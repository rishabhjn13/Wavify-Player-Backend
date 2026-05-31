from datetime import datetime
from typing import Optional
from fastapi import UploadFile
from fastapi.params import File
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _clean_text(v: str) -> str:
    """Strip and collapse internal whitespace."""
    return " ".join(v.strip().split())


def _validate_url(v: Optional[str]) -> Optional[str]:
    if v and not v.startswith(("http://", "https://")):
        raise ValueError("Must be a valid HTTP/HTTPS URL")
    return v


def _format_duration(duration_sec: int) -> str:
    m, s = divmod(duration_sec, 60)
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Songs
# ---------------------------------------------------------------------------

class SongAdd(BaseModel):
    """Input model — used when adding a song to the library or a playlist."""
    song_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=300)
    artist: str = Field(..., min_length=1, max_length=200)
    album: str = Field(default="", max_length=200)
    album_art: Optional[str] = Field(default=None, max_length=500)
    duration_sec: int = Field(default=0, ge=0, le=86400)
    search_string: str = Field(default="", max_length=500)

    @field_validator("song_id")
    @classmethod
    def strip_song_id(cls, v: str) -> str:
        return v.strip()

    @field_validator("title", "artist", "album")
    @classmethod
    def clean_text(cls, v: str) -> str:
        return _clean_text(v)

    @field_validator("album_art")
    @classmethod
    def validate_album_art(cls, v: Optional[str]) -> Optional[str]:
        return _validate_url(v)

    @model_validator(mode="after")
    def set_search_string(self) -> "SongAdd":
        if not self.search_string:
            self.search_string = f"{self.title} {self.artist}".strip()
        return self


class SongResponse(BaseModel):
    """Output model — returned by all song-related endpoints."""
    song_id: str
    title: str
    artist: str
    album: str = ""
    thumbnail: str = ""
    duration_sec: int = 0
    duration_formatted: str = ""
    created_at: Optional[str] = None

    @model_validator(mode="after")
    def compute_duration_formatted(self) -> "SongResponse":
        if not self.duration_formatted and self.duration_sec:
            self.duration_formatted = _format_duration(self.duration_sec)
        return self


# ---------------------------------------------------------------------------
# Liked Songs
# ---------------------------------------------------------------------------

class LikedSong(BaseModel):
    """Input model — used when liking a song."""
    song_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=300)
    artist: str = Field(..., min_length=1, max_length=200)
    album: str = Field(default="", max_length=200)
    thumbnail: str = Field(default="", max_length=500)
    duration_sec: int = Field(default=0, ge=0, le=86400)

    @field_validator("thumbnail")
    @classmethod
    def validate_thumbnail(cls, v: str) -> str:
        if v:
            _validate_url(v)
        return v


class LikedSongResponse(BaseModel):
    """Output model — returned by GET /liked-songs."""
    song_id: str
    title: str
    artist: str
    album: str = ""
    thumbnail: str = ""
    duration_sec: int = 0
    duration_formatted: str = ""
    liked_at: Optional[datetime] = None

    @model_validator(mode="after")
    def compute_duration_formatted(self) -> "LikedSongResponse":
        if not self.duration_formatted and self.duration_sec:
            self.duration_formatted = _format_duration(self.duration_sec)
        return self


# ---------------------------------------------------------------------------
# Playlists
# ---------------------------------------------------------------------------

class PlaylistCreate(BaseModel):
    """Input model — body fields for playlist creation (non-file fields)."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    color: str = Field(default="#6D28D9", max_length=20)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return _clean_text(v)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not v.startswith("#") or len(v) not in (4, 7):
            raise ValueError("Color must be a valid hex code e.g. #6D28D9")
        return v


class PlaylistResponse(BaseModel):
    """Output model — returned by GET /playlists and POST /playlists."""
    id: int
    name: str
    description: Optional[str] = None
    color: str = "#6D28D9"
    thumbnail: Optional[str] = None
    song_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Playlist Songs
# ---------------------------------------------------------------------------

class PlaylistSongResponse(BaseModel):
    """Output model — one entry from GET /playlists/{id}/songs."""
    song_id: str
    song_title: str
    position: int
    added_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Recently Played
# ---------------------------------------------------------------------------

class RecentlyPlayedResponse(BaseModel):
    """Output model — returned by GET /playlists/recently-played."""
    id: int
    name: str
    description: Optional[str] = None
    color: str = "#6D28D9"
    thumbnail: Optional[str] = None
    song_count: int = 0
    played_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Video Cache
# ---------------------------------------------------------------------------

class VideoCacheEntry(BaseModel):
    """
    Mirrors the video_cache table.

    NOTE: your schema is missing stream_url and cached_at columns
    which audio.py now writes. Add these to 01_schema.sql:

        ALTER TABLE video_cache ADD COLUMN stream_url TEXT;
        ALTER TABLE video_cache ADD COLUMN cached_at INTEGER;

    Or recreate the table as:

        CREATE TABLE IF NOT EXISTS video_cache (
            search_query TEXT PRIMARY KEY,
            video_id     TEXT,
            title        TEXT,
            uploader     TEXT,
            duration     INTEGER,
            thumbnail    TEXT,
            stream_url   TEXT,
            cached_at    INTEGER
        );
    """
    search_query: str
    video_id: Optional[str] = None
    title: Optional[str] = None
    uploader: Optional[str] = None
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    stream_url: Optional[str] = None
    cached_at: Optional[int] = None
