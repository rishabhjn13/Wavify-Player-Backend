from ytmusicapi import YTMusic
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Lazy initialization — don't crash the app if YTMusic fails to load
# ---------------------------------------------------------------------------

_yt: YTMusic | None = None


def _get_client() -> YTMusic:
    """
    Return the shared YTMusic client, initializing it on first use.
    Raises RuntimeError if initialization fails, so the caller gets a
    meaningful 503 rather than a module-level import crash.
    """
    global _yt
    if _yt is None:
        try:
            _yt = YTMusic()
            logger.info("YTMusic client initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize YTMusic client: %s", e, exc_info=True)
            raise RuntimeError(f"YTMusic client unavailable: {e}") from e
    return _yt


# ---------------------------------------------------------------------------
# Safe field extractors
# ---------------------------------------------------------------------------

def _extract_artist(item: dict) -> str:
    artists = item.get("artists") or []
    # Filter out entries without a name before joining
    names = [a["name"] for a in artists if a.get("name")]
    return ", ".join(names) if names else "Unknown Artist"


def _extract_album(item: dict) -> str:
    album = item.get("album")
    if isinstance(album, dict):
        return album.get("name") or "Single"
    return "Single"


def _extract_thumbnail(item: dict) -> str | None:
    thumbnails = item.get("thumbnails") or []
    # ytmusicapi returns thumbnails sorted smallest → largest, take the last
    for thumb in reversed(thumbnails):
        if isinstance(thumb, dict) and thumb.get("url"):
            return thumb["url"]
    return None


def _extract_duration(item: dict) -> int:
    """Return duration in seconds, defaulting to 0 if missing or non-integer."""
    raw = item.get("duration_seconds")
    try:
        return int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_youtube_metadata(query: str, limit: int = 1) -> list[dict]:
    """
    Search YTMusic for songs matching `query`.

    Returns a list of normalized track dicts.
    Raises RuntimeError if the YTMusic client is unavailable.
    Raises on unexpected errors so callers (search.py) can return proper 503s
    instead of silently getting an empty list treated as 404.
    """
    client = _get_client()  # Raises RuntimeError if client is down

    logger.info("YTMusic search: query='%s' limit=%d", query, limit)

    try:
        raw_results = client.search(query, filter="songs", limit=limit)
    except Exception as e:
        logger.error("YTMusic search failed for query='%s': %s", query, e, exc_info=True)
        raise  # Let search.py handle this as a 503

    results = []
    for item in raw_results:
        video_id = item.get("videoId")

        # Skip results with no playable ID — can happen when filter leaks non-song types
        if not video_id:
            logger.debug("Skipping result with no videoId: %s", item.get("title"))
            continue

        title = item.get("title") or "Unknown Track"
        artist = _extract_artist(item)

        results.append({
            "song_id": video_id,
            "title": title,
            "artist": artist,
            "album": _extract_album(item),
            "album_art": _extract_thumbnail(item),
            "duration_sec": _extract_duration(item),
            "search_string": f"{title} {artist}",
        })

    logger.info("YTMusic returned %d valid result(s) for query='%s'", len(results), query)
    return results
