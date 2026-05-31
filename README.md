<div align="center">

# 🎵 Wavify Backend Engine

**A self-hosted music streaming backend — run it locally, grab a coffee, and enjoy your music.**

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=flat)

</div>

---

## What is Wavify?

Wavify is a **local-first music streaming backend** that lets you search, play, download, and organize music — all from your own machine. It is not designed for serverless deployment (Vercel, Render, etc.) since it depends on system-level tools like `yt-dlp` and `ffmpeg`. Just run it locally and point your frontend at it.

### How it works

```
Search Query
    │
    ▼
ytmusicapi ──► Returns song metadata + song_id (YouTube video ID)
    │
    ▼
yt-dlp ──► Uses exact song_id to fetch direct stream URL from YouTube
    │                  ⚠️  This part is currently under maintenance
    ▼
Stream URL ──► Frontend plays audio directly from the URL
```

Songs are identified by their **exact YouTube video ID** — no ambiguous title-based search, no wrong song playing.

---

## Features

- 🎵 **Music Search** — Search any song via YouTube Music. Returns rich metadata including title, artist, album, thumbnail, and duration.
- ▶️ **Audio Streaming** — Stream songs directly via yt-dlp using exact YouTube video IDs. *(Under maintenance)*
- 📥 **Song Downloader** — Download any song as an MP3 to your local storage, completely free.
- 📋 **Playlist Management** — Create playlists with custom thumbnails, colors, and descriptions. Add, remove, and reorder songs. Edit or delete playlists anytime.
- ❤️ **Liked Songs** — Like songs and access them all in one place.
- 🕘 **Recently Played** — Tracks recently played songs and playlists automatically.
- ⚡ **Caching** — Aggressive caching across all features to minimize API calls and reduce response times.
- 📝 **Structured Logging** — Full request/response logging with request IDs, timing, and log levels. Logs available at `logs/app.log`.

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| **FastAPI** | REST API framework |
| **SQLite** | Local database (auto-created on first run) |
| **yt-dlp** | Stream URL extraction from YouTube |
| **ytmusicapi** | YouTube Music search & metadata |
| **mutagen** | Audio file metadata (MP3 tagging) |
| **uvicorn** | ASGI server |

---

## Getting Started

### Prerequisites

Make sure the following are installed on your system:

- Python 3.12+
- `yt-dlp` — [install guide](https://github.com/yt-dlp/yt-dlp#installation)
- `ffmpeg` — [install guide](https://ffmpeg.org/download.html)

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/rishabhjn13/Wavify-Player-Backend.git
cd wavify-backend-engine
```

**2. Create and activate a virtual environment**
```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Start the server**
```bash
uvicorn main:app --reload
```

That's it. The database file and all tables are created automatically on first run.

### Verify it's running

Open your browser and go to:
- **API Docs (Swagger):** `http://localhost:8000/docs`
- **Health check:** `http://localhost:8000/health`

---

## Project Structure

```
wavify-backend-engine/
├── main.py                  # App entry point, middleware
├── database.py              # DB connection & schema
├── models.py                # Pydantic request/response models
├── config.py                # App configuration & constants
├── requirements.txt
│
├── routes/
│   ├── audio.py             # Stream URL & song download endpoints
│   ├── playlists.py         # Playlist CRUD & thumbnail upload
│   └── search.py            # Song search via ytmusicapi
│
├── utils/
│   ├── logger.py            # Structured logger setup
│   └── yt_metadata_service.py  # ytmusicapi wrapper
│
├── static/
│   └── thumbnails/          # Uploaded playlist thumbnails
│
└── logs/
    └── app.log              # Application logs
```

---

## API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/search-metadata` | Search songs by query |
| `GET` | `/get-audio` | Get stream URL by song ID |
| `GET` | `/songs/last-played` | Get last played song |
| `GET` | `/playlists/` | Get all playlists |
| `POST` | `/playlists/` | Create a playlist |
| `POST` | `/playlists/{id}/thumbnail` | Upload playlist thumbnail |
| `POST` | `/playlists/{id}/songs` | Add song to playlist |
| `GET` | `/playlists/{id}/songs` | Get songs in a playlist |
| `DELETE` | `/playlists/{id}` | Delete a playlist |
| `GET` | `/playlists/recently-played` | Get recently played playlists |
| `POST` | `/playlists/{id}/played` | Mark playlist as played |

Full interactive docs available at `/docs` when the server is running.

---

## Logs

All requests are logged with request ID, method, path, status code, and response time.

```
logs/app.log
```

Example:
```
2026-05-31 21:00:12 - wavify.main - INFO  - [a1b2c3d4] GET /search-metadata
2026-05-31 21:00:13 - wavify.main - INFO  - [a1b2c3d4] 200 — 984ms
```



## Known Issues

- ⚠️ **Audio streaming via yt-dlp** is currently under maintenance due to YouTube's signature challenge requirements. A fix is in progress.

---

## Contributing

This project is personal and local-first, but PRs and issues are welcome. If you have a fix for the yt-dlp streaming issue especially — go ahead.

---

<div align="center">
Made with ☕ — meant to be run locally, not in the cloud.
</div>
