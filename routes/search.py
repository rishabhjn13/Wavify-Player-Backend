from fastapi import APIRouter, HTTPException, Query
from utils.yt_metadata_service import search_youtube_metadata
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["search"])

MAX_SEARCH_LIMIT = 25  # Hard cap — prevents abuse / yt-dlp hammering


def _run_search(query: str, limit: int) -> list:
    """
    Shared search logic for both endpoints.
    Validates input, calls the metadata service, and handles errors uniformly.
    """
    query = query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter cannot be empty")

    # Clamp limit defensively even if Query(le=...) already does it
    limit = max(1, min(limit, MAX_SEARCH_LIMIT))

    logger.info("Searching YouTube metadata: query='%s' limit=%d", query, limit)

    try:
        results = search_youtube_metadata(query, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("search_youtube_metadata failed for query='%s': %s", query, e, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Search service is temporarily unavailable. Please try again.",
        )

    if not results:
        logger.warning("No results found for query='%s'", query)
        raise HTTPException(status_code=404, detail="No matching tracks found")

    logger.info("Returning %d result(s) for query='%s'", len(results), query)
    return results


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/search-metadata")
def search_metadata(query: str = Query(..., min_length=1, max_length=200)):
    """Search YouTube and return the single best matching track."""
    return _run_search(query, limit=1)[0]


@router.get("/search-metadata-bylimit")
def search_metadata_by_limit(
    query: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=MAX_SEARCH_LIMIT),
):
    """Search YouTube and return up to `limit` matching tracks."""
    return _run_search(query, limit=limit)
