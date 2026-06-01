import time
from fastapi import APIRouter, HTTPException
from yt_dlp import YoutubeDL
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from database import get_db_ctx
from models import SongAdd
from config import YDL_MAX_RETRIES, STREAM_URL_TTL
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["audio"])


# ---------------------------------------------------------------------------
# yt-dlp helpers
# ---------------------------------------------------------------------------

YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "skip_download": True,
    "extract_flat": False,
    "cookiesfrombrowser": ("brave",),
    "youtube_include_dash_manifest": False,
}


@retry(
    retry=retry_if_exception_type((Exception,)),
    stop=stop_after_attempt(YDL_MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _extract_info(url: str) -> dict:
    """
    Call yt-dlp with exponential backoff retries.
    Accepts a full YouTube URL (not a search query) for exact resolution.
    """
    with YoutubeDL(YDL_OPTS) as ydl:
        return ydl.extract_info(url, download=False)


def _pick_stream_url(video: dict) -> str | None:
    """Pick best available stream URL — audio-only preferred, falls back to any format."""
    formats = video.get("formats", [])

    # Priority 1: audio-only, highest bitrate
    audio_only = [
        f for f in formats
        if f.get("acodec") != "none" and f.get("vcodec") == "none" and f.get("url")
    ]
    if audio_only:
        return max(audio_only, key=lambda f: f.get("abr") or 0)["url"]

    # Priority 2: any format with audio
    with_audio = [
        f for f in formats
        if f.get("acodec") != "none" and f.get("url")
    ]
    if with_audio:
        return max(with_audio, key=lambda f: f.get("abr") or 0)["url"]

    # Priority 3: top-level url fallback
    if video.get("url"):
        return video["url"]

    return None

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_cached(song_id: str) -> dict | None:
    """Return cached result if it exists and hasn't expired."""
    with get_db_ctx() as db:
        row = db.execute(
            """
            SELECT song_id, title, uploader, duration, thumbnail, stream_url, cached_at
            FROM video_cache
            WHERE search_query = ?
            """,
            (song_id,),
        ).fetchone()

    if not row:
        return None

    age = time.time() - (row["cached_at"] or 0)
    if age > STREAM_URL_TTL:
        logger.info("Cache expired for song_id '%s' (age: %ds)", song_id, int(age))
        return None

    logger.info("Cache hit for song_id '%s'", song_id)
    return dict(row)


def _set_cache(song_id: str, video: dict, stream_url: str) -> None:
    """Upsert a video result into the cache, keyed by song_id."""
    with get_db_ctx() as db:
        db.execute(
            """
            INSERT OR REPLACE INTO video_cache
            (search_query, song_id, title, uploader, duration, thumbnail, stream_url, cached_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                song_id,
                video.get("song_id"),
                video.get("title"),
                video.get("uploader"),
                video.get("duration"),
                video.get("thumbnail"),
                stream_url,
                int(time.time()),
            ),
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/get-audio")
def get_audio(song_id: str):
    """
    Fetch a direct stream URL by exact YouTube video ID.
    No search — resolves the exact video, no ambiguity.
    """
    if not song_id or not song_id.strip():
        raise HTTPException(status_code=400, detail="Missing song_id parameter.")

    song_id = song_id.strip()
    youtube_url = f"https://www.youtube.com/watch?v={song_id}"
    logger.info("Audio requested for song_id: '%s'", song_id)

    # 1. Cache-first (keyed by song_id)
    cached = _get_cached(song_id)
    if cached:
        return {
            "song_id": cached["song_id"],
            "title": cached["title"],
            "uploader": cached["uploader"],
            "duration": cached["duration"],
            "thumbnail": cached["thumbnail"],
            "stream_url": cached["stream_url"],
            "source": "cache",
        }

    # 2. Extract via yt-dlp using exact YouTube URL (no search ambiguity)
    try:
        video = _extract_info(youtube_url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("yt-dlp extraction failed for song_id '%s' after %d retries: %s", song_id, YDL_MAX_RETRIES, e, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Could not fetch audio. The source may be unavailable — please try again.",
        )

    if not video:
        logger.warning("No yt-dlp result for song_id: '%s'", song_id)
        raise HTTPException(status_code=404, detail="No results found for this song.")

    logger.info("Resolved video: '%s' by '%s'", video.get("title"), video.get("uploader"))

    # 3. Extract stream URL
    stream_url = _pick_stream_url(video)
    if not stream_url:
        logger.error("Could not extract stream URL for song_id: %s", song_id)
        raise HTTPException(status_code=500, detail="Could not extract a playable stream URL.")

    # 4. Cache the result (keyed by song_id)
    try:
        _set_cache(song_id, video, stream_url)
    except Exception as e:
        logger.warning("Failed to cache result for song_id '%s': %s", song_id, e)

    return {
        "song_id": video.get("id"),
        "title": video.get("title"),
        "uploader": video.get("uploader"),
        "duration": video.get("duration"),
        "thumbnail": video.get("thumbnail"),
        "stream_url": stream_url,
        "source": "live",
    }


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
