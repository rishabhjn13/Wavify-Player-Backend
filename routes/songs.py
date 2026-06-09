from fastapi import APIRouter, HTTPException

from database import get_db_ctx
from models import LikedSong, SongAdd
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["songs"])


@router.get("/recently-added")
def get_recently_added_songs():
    with get_db_ctx() as db:
        rows = db.execute("""
            SELECT song_id, title, artist, album, thumbnail, duration_sec
            FROM songs
            ORDER BY created_at DESC
            LIMIT 5
        """).fetchall()
    return [dict(row) for row in rows]

@router.get("/liked-songs")
def get_liked_songs():
    with get_db_ctx() as db:
        rows = db.execute("""
            SELECT song_id, title, artist, album, thumbnail, duration_sec, liked_at
            FROM liked_songs
            ORDER BY liked_at DESC
        """).fetchall()
    return [dict(row) for row in rows]

@router.get("/songs/last-played")
def get_last_played():
    with get_db_ctx() as db:
        row = db.execute(
            """
            SELECT song_id, title, artist, album, thumbnail, duration_sec
            FROM songs
            ORDER BY created_at DESC
            LIMIT 1
            """,
        ).fetchone()

        if not row:
            return None

        return dict(row)

@router.get("/songs/{song_id}")
def get_song(song_id: str):
    with get_db_ctx() as db:
        row = db.execute(
            "SELECT song_id, title, artist, album, thumbnail, duration_sec FROM songs WHERE song_id = ?",
            (song_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Song not found")
        return dict(row)

@router.post("/songs")
def add_song(song: SongAdd):
    logger.info("Adding song: '%s' by '%s'", song.title, song.artist)
    try:
        with get_db_ctx() as db:
            db.execute(
                """
                INSERT OR IGNORE INTO songs (song_id, title, artist, album, thumbnail, duration_sec, search_string)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (song.song_id, song.title, song.artist, song.album, song.album_art, song.duration_sec, song.search_string),
            )
            logger.info("Song added: '%s' (%s)", song.title, song.song_id)
            return {"message": f"'{song.title}' added to songs", "song_id": song.song_id}
    except Exception as e:
        logger.error("Failed to add song '%s': %s", song.song_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save song.")

