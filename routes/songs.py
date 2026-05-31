from fastapi import APIRouter, HTTPException

from database import get_db_ctx
from models import LikedSong
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["songs"])


@router.get("/recently-added")
def get_recently_added_songs():
    with get_db_ctx() as db:
        rows = db.execute("""
            SELECT id, title, artist, album, thumbnail, duration_sec
            FROM songs
            ORDER BY created_at DESC
            LIMIT 5
        """).fetchall()
    return [dict(row) for row in rows]


@router.get("/liked-songs")
def get_liked_songs():
    with get_db_ctx() as db:
        rows = db.execute("""
            SELECT id, title, artist, album, thumbnail, duration_sec, liked_at
            FROM liked_songs
            ORDER BY liked_at DESC
        """).fetchall()
    return [dict(row) for row in rows]


@router.post("/liked-songs")
def like_song(song: LikedSong):
    logger.info("Liking song: '%s' (%s)", song.title, song.id)
    try:
        with get_db_ctx() as db:
            db.execute(
                """
                INSERT OR IGNORE INTO liked_songs (id, title, artist, album, thumbnail, duration_sec)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (song.id, song.title, song.artist, song.album, song.thumbnail, song.duration_sec),
            )
        return {"message": f"'{song.title}' added to liked songs", "id": song.id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to like song '%s': %s", song.id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save liked song.")


@router.delete("/liked-songs/{song_id}")
def unlike_song(song_id: str):
    logger.info("Unliking song: %s", song_id)
    try:
        with get_db_ctx() as db:
            row = db.execute(
                "SELECT id FROM liked_songs WHERE id = ?", (song_id,)
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Song not found in liked songs")

            db.execute("DELETE FROM liked_songs WHERE id = ?", (song_id,))

        logger.info("Song unliked: %s", song_id)
        return {"message": "Song removed from liked songs", "id": song_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to unlike song '%s': %s", song_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to remove liked song.")
