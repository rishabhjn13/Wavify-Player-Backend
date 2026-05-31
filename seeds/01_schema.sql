-- Video Cache
CREATE TABLE IF NOT EXISTS video_cache (
    search_query TEXT PRIMARY KEY,
    song_id     TEXT,
    title        TEXT,
    uploader     TEXT,
    duration     INTEGER,
    thumbnail    TEXT,
    stream_url   TEXT,      -- added: audio.py caches the stream URL
    cached_at    INTEGER    -- added: unix timestamp for TTL checks
);

-- Songs
CREATE TABLE IF NOT EXISTS songs (
    song_id           TEXT PRIMARY KEY,
    title        TEXT,
    artist       TEXT,
    album        TEXT,
    thumbnail    TEXT,
    duration_sec INTEGER,
    search_string TEXT,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Playlists
CREATE TABLE IF NOT EXISTS playlists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    color       TEXT DEFAULT '#6D28D9',
    thumbnail   TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Playlist <-> Songs junction
CREATE TABLE IF NOT EXISTS playlist_songs (
    playlist_id INTEGER NOT NULL,
    song_id     TEXT NOT NULL,   -- fixed: was INTEGER, songs.id is TEXT
    song_title  TEXT NOT NULL,
    position    INTEGER NOT NULL,
    added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (playlist_id, song_id),
    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
    FOREIGN KEY (song_id)     REFERENCES songs(id)     ON DELETE CASCADE
);

-- Recently Played
CREATE TABLE IF NOT EXISTS recently_played (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER NOT NULL,
    played_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
);

-- Liked Songs
CREATE TABLE IF NOT EXISTS liked_songs (
    song_id           TEXT PRIMARY KEY,
    title        TEXT,
    artist       TEXT,
    album        TEXT,
    thumbnail    TEXT,
    duration_sec INTEGER,
    liked_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id) REFERENCES songs(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_playlist_songs_song     ON playlist_songs(song_id);
CREATE INDEX IF NOT EXISTS idx_playlist_songs_playlist ON playlist_songs(playlist_id);
CREATE INDEX IF NOT EXISTS idx_recently_played_playlist ON recently_played(playlist_id);
CREATE INDEX IF NOT EXISTS idx_liked_songs_liked_at    ON liked_songs(liked_at);
CREATE INDEX IF NOT EXISTS idx_video_cache_cached_at   ON video_cache(cached_at);  -- added: for TTL sweeps

-- Trigger: keep updated_at current on playlists
CREATE TRIGGER IF NOT EXISTS playlists_updated_at
AFTER UPDATE ON playlists
BEGIN
    UPDATE playlists SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
