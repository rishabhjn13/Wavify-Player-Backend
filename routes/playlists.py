import shutil
import os
from fastapi import APIRouter, HTTPException, File, Form, UploadFile
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime
import sqlite3

from config import UPLOAD_DIR
from database import get_db
from models import SongAdd

router = APIRouter(prefix="/playlists", tags=["playlists"])

os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/")
async def create_playlist(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    color: str = Form("#6D28D9"),
    thumbnail: Optional[UploadFile] = File(None)
):
    thumbnail_path = None

    if thumbnail and thumbnail.filename:
        try:
            file_ext = thumbnail.filename.split(".")[-1].lower()
            safe_name = "".join(c for c in name if c.isalnum() or c in " _-")[:40]
            timestamp = int(os.times().system * 1000)
            filename = f"pl_{timestamp}_{safe_name}.{file_ext}"

            file_path = os.path.join(UPLOAD_DIR, filename)

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(thumbnail.file, buffer)

            thumbnail_path = f"/static/thumbnails/{filename}"
        except Exception as e:
            print(f"⚠️ Thumbnail error: {e}")

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO playlists (name, description, color, thumbnail)
            VALUES (?, ?, ?, ?)
        """, (name, description, color, thumbnail_path))

        playlist_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return JSONResponse(content={
            "id": playlist_id,
            "message": "Playlist created successfully",
            "thumbnail": thumbnail_path
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
def get_all_playlists():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, COUNT(ps.song_id) as song_count
        FROM playlists p
        LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
    """)
    playlists = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return playlists


@router.get("/{playlist_id}/songs")
def get_playlist_songs(playlist_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT song_id, song_title, position FROM playlist_songs
        WHERE playlist_id = ?
        ORDER BY position ASC
    """, (playlist_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"song_id": row[0], "song_title": row[1], "position": row[2]} for row in rows]


@router.post("/{playlist_id}/songs")
def add_song_to_playlist(playlist_id: int, song: SongAdd):
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM playlists WHERE id = ?", (playlist_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Playlist not found")

        print(f"🔍 Adding song {song.song_id} → Playlist {playlist_id}")

        # Check if already exists
        cursor.execute("""
        SELECT 1 FROM playlist_songs
        WHERE playlist_id = ? AND song_id = ?
        """, (playlist_id, song.song_id))

        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Song already in playlist")

        # Convert duration_sec safely
        duration_sec = int(song.duration_sec) if song.duration_sec else 0

        # Upsert into songs table
        cursor.execute("""
        INSERT INTO songs (id, title, artist, album, thumbnail,
        duration_sec, search_string, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
        title = excluded.title,
        artist = excluded.artist,
        album = excluded.album,
        thumbnail = excluded.thumbnail,
        duration_sec = excluded.duration_sec,
        search_string = excluded.search_string
        """, (
            song.song_id,
            song.title,
            song.artist,
            song.album,
            song.album_art,
            duration_sec,                       # ← Ensured integer
            f"{song.title} {song.artist} {song.album}".lower(),
            datetime.now().isoformat()
        ))

        # Get next position
        cursor.execute("SELECT MAX(position) FROM playlist_songs WHERE playlist_id = ?", (playlist_id,))
        max_pos = cursor.fetchone()[0] or 0
        position = max_pos + 1

        # Insert into playlist_songs
        cursor.execute("""
        INSERT INTO playlist_songs (playlist_id, song_id, song_title, position)
        VALUES (?, ?, ?, ?)
        """, (playlist_id, song.song_id, song.title, position))

        conn.commit()
        print(f"✅ Song added successfully at position {position}")
        return {"message": "Song added successfully", "position": position}

    except sqlite3.Error as e:
        conn.rollback()
        print(f"❌ Database Error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error in add_song_to_playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.delete("/{playlist_id}")
async def delete_playlist(playlist_id: int):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, thumbnail FROM playlists WHERE id = ?", (playlist_id,))
        playlist = cursor.fetchone()

        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        playlist_name = playlist["name"]
        thumbnail_path = playlist["thumbnail"]

        cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        conn.commit()
        conn.close()

        # Delete thumbnail file if exists
        if thumbnail_path:
            try:
                filename = thumbnail_path.split("/")[-1]
                file_full_path = os.path.join(UPLOAD_DIR, filename)
                if os.path.exists(file_full_path):
                    os.remove(file_full_path)
            except Exception as e:
                print(f"⚠️ Could not delete thumbnail: {e}")

        return {"message": f"Playlist '{playlist_name}' deleted successfully", "id": playlist_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))