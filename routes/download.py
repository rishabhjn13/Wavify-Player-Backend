import io
import os
import re
import tempfile

import requests as req
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from mutagen.id3 import APIC, ID3, TPE1, TIT2
import yt_dlp

from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["download"])

THUMBNAIL_FETCH_TIMEOUT = 10  # seconds
VALID_VIDEO_ID = re.compile(r'^[a-zA-Z0-9_-]{6,16}$')


def _validate_video_id(song_id: str) -> None:
    """Guard against path traversal / injection via video_id."""
    if not VALID_VIDEO_ID.match(song_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid song_id format.",
        )


def _embed_tags(mp3_path: str, title: str, artist: str, thumbnail: str | None) -> None:
    """Embed ID3 tags into the downloaded MP3. Non-fatal on failure."""
    try:
        tags = ID3(mp3_path)
        tags["TIT2"] = TIT2(encoding=3, text=title)
        tags["TPE1"] = TPE1(encoding=3, text=artist)

        if thumbnail:
            try:
                resp = req.get(thumbnail, timeout=THUMBNAIL_FETCH_TIMEOUT)
                resp.raise_for_status()
                mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
                tags["APIC"] = APIC(
                    encoding=3, mime=mime, type=3, desc="Cover", data=resp.content
                )
            except Exception as e:
                # Thumbnail failure is non-fatal — skip cover art, still serve the file
                logger.warning("Could not fetch thumbnail for '%s': %s", title, e)

        tags.save(mp3_path)
    except Exception as e:
        logger.warning("Could not embed ID3 tags for '%s': %s", title, e)


@router.get("/download")
def download_track(
    song_id: str = Query(..., min_length=1, max_length=20),
    title: str = Query(default="track", max_length=200),
    artist: str = Query(default="", max_length=200),
    thumbnail: str = Query(default="", max_length=500),
):
    """
    Download a YouTube track as an MP3 with embedded ID3 tags.
    Streams the file back to the client.
    """
    _validate_video_id(song_id)

    url = f"https://www.youtube.com/watch?v={song_id}"
    safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)  # Sanitize for Content-Disposition
    logger.info("Download requested: song_id='%s' title='%s'", song_id, title)

    try:
        with tempfile.TemporaryDirectory() as tmp:
            mp3_path = os.path.join(tmp, f"{song_id}.mp3")

            opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "quiet": True,
                "no_warnings": True,
            }

            # BUG FIX: single download call — original ran yt-dlp twice
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            if not os.path.exists(mp3_path):
                logger.error("MP3 not found after download: %s", mp3_path)
                raise HTTPException(
                    status_code=500,
                    detail="Download failed — could not produce an MP3 file.",
                )

            _embed_tags(mp3_path, title, artist, thumbnail or None)

            # Read into memory inside the tempdir context before it's deleted
            with open(mp3_path, "rb") as f:
                data = f.read()

        logger.info(
            "Download complete: '%s' (%s) — %.2fMB",
            title, song_id, len(data) / (1024 * 1024),
        )

        return StreamingResponse(
            io.BytesIO(data),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_title}.mp3"',
                "Content-Length": str(len(data)),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Download failed for song_id='%s': %s", song_id, e, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Download failed. The track may be unavailable or region-locked.",
        )
