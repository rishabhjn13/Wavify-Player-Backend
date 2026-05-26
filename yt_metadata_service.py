from ytmusicapi import YTMusic

# Initialize the engine once at the top of the file
yt = YTMusic()

def search_youtube_metadata(query: str):
    """
    Searches YouTube Music specifically for songs, returning clean
    titles, artist strings, and high-res square album art thumbnails.
    """
    try:
        # We filter specifically for "songs" to avoid random vlogs or live streams
        search_results = yt.search(query, filter="songs", limit=10)

        results = []
        for item in search_results:
            # Grab the absolute highest-resolution image available in the array
            thumbnails = item.get("thumbnails", [])
            album_art = thumbnails[-1]["url"] if thumbnails else None

            # Combine multiple artists if they exist (e.g., "The Weeknd, Daft Punk")
            artists_list = item.get("artists", [])
            artist_string = ", ".join([a.get("name") for a in artists_list]) if artists_list else "Unknown Artist"

            title = item.get("title", "Unknown Track")

            results.append({
                "id": item.get("videoId"), # This is the unique YouTube Video ID
                "title": title,
                "artist": artist_string,
                "album": item.get("album", {}).get("name") if item.get("album") else "Single",
                "album_art": album_art, # Direct link for Android's Coil image loader
                "duration_sec": item.get("duration_seconds"),
                # This search string drops directly into your /get-audio SQLite cache!
                "search_string": f"{title} {artist_string}"
            })

            return results

    except Exception as e:
        # If something breaks, pass the error message upwards
        print(f"Error inside ytmusicapi wrapper: {str(e)}")
        return []