from pydantic import BaseModel
from typing import Optional

class SongAdd(BaseModel):
    song_id: str
    title: str
    artist: str
    album: str = ""
    album_art: Optional[str] = None
    duration_sec: int = 0