import os
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, File, UploadFile

from config import UPLOAD_DIR
from database import get_db_ctx
# NOTE: Assuming PlaylistUpdate is added to your models to support optional patch fields
from models import PlaylistCreate, PlaylistResponse, SongAdd, PlaylistUpdate 
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/playlists", tags=["playlists"])

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_THUMBNAIL_SIZE_MB = 5
MAX_PLAYLIST_FETCH_LIMIT = 10

# ---------------------------------------------------------------------------
# Thumbnail helpers
# ---------------------------------------------------------------------------

async def _save_thumbnail(name: str, thumbnail: UploadFile) -> str | None:
    """
    Validate and save an uploaded thumbnail.
    Returns the static URL path, or None if no file provided.
    Raises HTTPException on invalid file type or size.
    """
    if not thumbnail or not thumbnail.filename:
        return None

    file_ext = thumbnail.filename.rsplit(".", 1)[-1].lower()
    if file_ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image type '.{file_ext}'. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
        )

    # Read content to check size
    content = await thumbnail.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_THUMBNAIL_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Thumbnail too large ({size_mb:.1f}MB). Max allowed: {MAX_THUMBNAIL_SIZE_MB}MB",
        )

    safe_name = "".join(c for c in name if c.isalnum() or c in " _-")[:40]
    # BUG FIX: os.times().system is CPU time, not wall clock — use time.time()
    filename = f"pl_{int(time.time() * 1000)}_{safe_name}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    try:
        with open(file_path, "wb") as f:
            f.write(content)
        logger.info("Thumbnail saved: %s", filename)
    except OSError as e:
        logger.error("Failed to save thumbnail '%s': %s", filename, e)
        raise HTTPException(status_code=500, detail="Failed to save thumbnail.")

    return f"/static/thumbnails/{filename}"


def _delete_thumbnail(thumbnail_path: str | None) -> None:
    """Best-effort thumbnail file deletion — logs warning on failure, never raises."""
    if not thumbnail_path:
        return
    try:
        filename = thumbnail_path.rsplit("/", 1)[-1]
        full_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(full_path):
            os.remove(full_path)
            logger.info("Deleted thumbnail: %s", filename)
    except OSError as e:
        logger.warning("Could not delete thumbnail '%s': %s", thumbnail_path, e)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[PlaylistResponse])
def get_all_playlists():
    with get_db_ctx() as db:
        rows = db.execute("""
        SELECT p.*, COUNT(ps.song_id) as song_count
        FROM playlists p
        LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
        """).fetchall()
        return [dict(row) for row in rows]

@router.post("/", response_model=PlaylistResponse, status_code=201)
def create_playlist(pl: PlaylistCreate):
    logger.info("Creating playlist: '%s'", pl.name)

    try:
        with get_db_ctx() as db:
            cursor = db.execute(
                "INSERT INTO playlists (name, description, color) VALUES (?, ?, ?)",
                (pl.name, pl.description, pl.color),
            )
            playlist_id = cursor.lastrowid
            row = db.execute(
                "SELECT * FROM playlists WHERE id = ?", (playlist_id,)
            ).fetchone()

        logger.info("Playlist created: '%s' (id=%s)", pl.name, playlist_id)
        return {**dict(row), "song_count": 0}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create playlist '%s': %s", pl.name, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create playlist.")


@router.patch("/{playlist_id}", response_model=PlaylistResponse)
def update_playlist(playlist_id: int, pl: PlaylistUpdate):
    """Dynamically updates playlist text details (name, description, color)."""
    logger.info("Updating playlist %d", playlist_id)
    
    # Extract only fields that were explicitly provided
    update_data = pl.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    try:
        with get_db_ctx() as db:
            # Check playlist existence
            if not db.execute("SELECT 1 FROM playlists WHERE id = ?", (playlist_id,)).fetchone():
                raise HTTPException(status_code=404, detail="Playlist not found")

            # Dynamically build UPDATE query string
            set_clause = ", ".join([f"{key} = ?" for key in update_data.keys()])
            values = list(update_data.values()) + [playlist_id]

            db.execute(f"UPDATE playlists SET {set_clause} WHERE id = ?", tuple(values))

            # Fetch updated row and song count to return
            updated_row = db.execute(
                "SELECT * FROM playlists WHERE id = ?", (playlist_id,)
            ).fetchone()
            song_count = db.execute(
                "SELECT COUNT(*) FROM playlist_songs WHERE playlist_id = ?",
                (playlist_id,)
            ).fetchone()[0]

        logger.info("Playlist %d updated successfully.", playlist_id)
        return {**dict(updated_row), "song_count": song_count}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update playlist %d: %s", playlist_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update playlist.")
    

@router.post("/{playlist_id}/thumbnail", response_model=PlaylistResponse)
async def upload_thumbnail(
    playlist_id: int,
    thumbnail: UploadFile = File(...),
):
    with get_db_ctx() as db:
        row = db.execute(
            "SELECT * FROM playlists WHERE id = ?", (playlist_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Playlist not found.")

    old_thumbnail = row["thumbnail"]
    thumbnail_path = await _save_thumbnail(str(playlist_id), thumbnail)

    try:
        with get_db_ctx() as db:
            db.execute(
                "UPDATE playlists SET thumbnail = ? WHERE id = ?",
                (thumbnail_path, playlist_id),
            )
            updated_row = db.execute(
                "SELECT * FROM playlists WHERE id = ?", (playlist_id,)
            ).fetchone()
            song_count = db.execute(
                "SELECT COUNT(*) FROM playlist_songs WHERE playlist_id = ?",
                (playlist_id,)
            ).fetchone()[0]

        _delete_thumbnail(old_thumbnail)
        return {**dict(updated_row), "song_count": song_count}

    except Exception as e:
        _delete_thumbnail(thumbnail_path)  
        logger.error("Failed to upload thumbnail for playlist %s: %s", playlist_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload thumbnail.")

@router.get("/recently-played")
def get_recently_played(limit: int = 5):
    if limit < 1 or limit > MAX_PLAYLIST_FETCH_LIMIT:
        raise HTTPException(status_code=400, detail=f"Limit must be between 1 and {MAX_PLAYLIST_FETCH_LIMIT}")
    with get_db_ctx() as db:
        rows = db.execute("""
            SELECT DISTINCT p.*, rp.played_at, COUNT(ps.song_id) as song_count
            FROM recently_played rp
            JOIN playlists p ON p.id = rp.playlist_id
            LEFT JOIN playlist_songs ps ON ps.playlist_id = p.id
            GROUP BY p.id
            ORDER BY rp.played_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(row) for row in rows]


@router.get("/{playlist_id}/songs")
def get_playlist_songs(playlist_id: int):
    with get_db_ctx() as db:
        if not db.execute("SELECT 1 FROM playlists WHERE id = ?", (playlist_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Playlist not found")

        rows = db.execute("""
            SELECT song_id, song_title, position
            FROM playlist_songs
            WHERE playlist_id = ?
            ORDER BY position ASC
        """, (playlist_id,)).fetchall()

    return [{"song_id": r["song_id"], "song_title": r["song_title"], "position": r["position"]} for r in rows]


@router.post("/{playlist_id}/songs")
def add_song_to_playlist(playlist_id: int, song: SongAdd):
    logger.info("Adding song '%s' to playlist %d", song.song_id, playlist_id)

    try:
        with get_db_ctx() as db:
            if not db.execute("SELECT 1 FROM playlists WHERE id = ?", (playlist_id,)).fetchone():
                raise HTTPException(status_code=404, detail="Playlist not found")

            if db.execute(
                "SELECT 1 FROM playlist_songs WHERE playlist_id = ? AND song_id = ?",
                (playlist_id, song.song_id),
            ).fetchone():
                raise HTTPException(status_code=409, detail="Song already in playlist")

            db.execute(
                """
                INSERT INTO songs (song_id, title, artist, album, thumbnail, duration_sec, search_string, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(song_id) DO UPDATE SET
                    title = excluded.title,
                    artist = excluded.artist,
                    album = excluded.album,
                    thumbnail = excluded.thumbnail,
                    duration_sec = excluded.duration_sec,
                    search_string = excluded.search_string
                """,
                (
                    song.song_id,
                    song.title,
                    song.artist,
                    song.album,
                    song.album_art,
                    song.duration_sec,
                    song.search_string or f"{song.title} {song.artist} {song.album}".lower(),
                    datetime.now().isoformat(),
                ),
            )

            max_pos = db.execute(
                "SELECT COALESCE(MAX(position), 0) FROM playlist_songs WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()[0]
            position = max_pos + 1

            db.execute(
                "INSERT INTO playlist_songs (playlist_id, song_id, song_title, position) VALUES (?, ?, ?, ?)",
                (playlist_id, song.song_id, song.title, position),
            )

        logger.info("Song '%s' added to playlist %d at position %d", song.song_id, playlist_id, position)
        return {"message": "Song added successfully", "position": position}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to add song '%s' to playlist %d: %s", song.song_id, playlist_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add song to playlist.")


@router.delete("/{playlist_id}/songs/{song_id}")
def remove_song_from_playlist(playlist_id: int, song_id: str):
    """Removes a song from a playlist and maintains consistent incremental tracking order positions."""
    logger.info("Removing song '%s' from playlist %d", song_id, playlist_id)

    try:
        with get_db_ctx() as db:
            if not db.execute("SELECT 1 FROM playlists WHERE id = ?", (playlist_id,)).fetchone():
                raise HTTPException(status_code=404, detail="Playlist not found")

            # Check if song exists in the playlist and fetch its current position
            target_song = db.execute(
                "SELECT position FROM playlist_songs WHERE playlist_id = ? AND song_id = ?",
                (playlist_id, song_id),
            ).fetchone()

            if not target_song:
                raise HTTPException(status_code=404, detail="Song not found in this playlist")

            removed_position = target_song["position"]

            # Remove the song mapping
            db.execute(
                "DELETE FROM playlist_songs WHERE playlist_id = ? AND song_id = ?",
                (playlist_id, song_id),
            )

            # Re-order track sequential indices to patch structural sequence gap
            db.execute(
                """
                UPDATE playlist_songs 
                SET position = position - 1 
                WHERE playlist_id = ? AND position > ?
                """,
                (playlist_id, removed_position),
            )

        logger.info("Song '%s' successfully removed from playlist %d", song_id, playlist_id)
        return {"message": "Song removed successfully from playlist"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to remove song '%s' from playlist %d: %s", song_id, playlist_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to remove song from playlist.")


@router.post("/{playlist_id}/played")
def mark_played(playlist_id: int):
    try:
        with get_db_ctx() as db:
            if not db.execute("SELECT 1 FROM playlists WHERE id = ?", (playlist_id,)).fetchone():
                raise HTTPException(status_code=404, detail="Playlist not found")

            db.execute("INSERT INTO recently_played (playlist_id) VALUES (?)", (playlist_id,))

        logger.info("Playlist %d marked as played", playlist_id)
        return {"message": "Marked as played"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to mark playlist %d as played: %s", playlist_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to mark playlist as played.")


@router.delete("/{playlist_id}")
async def delete_playlist(playlist_id: int):
    logger.info("Deleting playlist %d", playlist_id)

    try:
        with get_db_ctx() as db:
            row = db.execute(
                "SELECT id, name, thumbnail FROM playlists WHERE id = ?", (playlist_id,)
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Playlist not found")

            playlist_name = row["name"]
            thumbnail_path = row["thumbnail"]

            db.execute("DELETE FROM playlist_songs WHERE playlist_id = ?", (playlist_id,))
            db.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))

        _delete_thumbnail(thumbnail_path)

        logger.info("Playlist '%s' (id=%d) deleted", playlist_name, playlist_id)
        return {"message": f"Playlist '{playlist_name}' deleted successfully", "id": playlist_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete playlist %d: %s", playlist_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete playlist.")