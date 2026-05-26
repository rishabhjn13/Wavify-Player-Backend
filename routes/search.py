from fastapi import APIRouter, HTTPException
from yt_metadata_service import search_youtube_metadata

router = APIRouter(tags=["search"])

@router.get("/search-metadata")
def search_metadata(query: str):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter cannot be empty")
        
    results = search_youtube_metadata(query)
    
    if not results:
        raise HTTPException(status_code=404, detail="No matching tracks found")
        
    return results