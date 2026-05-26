from fastapi import APIRouter, HTTPException
import sqlite3
from yt_dlp import YoutubeDL
from database import get_db

router = APIRouter(tags=["audio"])

@router.get("/get-audio")
def get_audio(track: str):
    """
    Search for one track and return full metadata + direct stream URL
    """
    if not track:
        raise HTTPException(status_code=400, detail="Missing track parameter")

    query = track.strip().lower()

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'skip_download': True,
        'extract_flat': False,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # Search for single best match
            search_data = ydl.extract_info(f"ytsearch1:{query}", download=False)

            if not search_data or 'entries' not in search_data or not search_data['entries']:
                raise HTTPException(status_code=404, detail="No results found")

            video = search_data['entries'][0]  # Take the best match
            # // Write log to logs/audio.log
            
            with open("logs/audio.log", "a") as log_file:
                log_file.write(f"Search query: '{query}' - Found video: '{video.get('title')}' by '{video.get('uploader')}'\n")
            
            video_id = video.get("id")
            title = video.get("title")
            uploader = video.get("uploader")
            duration = video.get("duration")
            thumbnail = video.get("thumbnail")

            # Extract direct stream URL
            stream_url = None
            if video.get('url'):
                stream_url = video.get('url')
            elif video.get('formats'):
                # Pick best audio-only format
                audio_formats = [f for f in video['formats']
                if f.get('acodec') != 'none' and f.get('url')]
                if audio_formats:
                    stream_url = audio_formats[0].get('url')

                    if not stream_url:
                        raise HTTPException(status_code=500, detail="Could not extract stream URL")

                    # Cache the metadata
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO video_cache
            (search_query, video_id, title, uploader, duration, thumbnail)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (title.strip().lower(), video_id, title, uploader, duration, thumbnail))
            conn.commit()
            conn.close()

            # Return clean response
            return {
            "id": video_id,
            "title": title,
            "duration": duration,
            "stream_url": stream_url,
            }

    except Exception as e:
        print(f"Error in get-audio for '{track}': {e}")
        raise HTTPException(status_code=500, detail=str(e))