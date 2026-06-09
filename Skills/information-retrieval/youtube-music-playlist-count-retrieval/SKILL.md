---
name: youtube-music-playlist-count-retrieval
description: "A generalized procedure for querying the YouTube Music API to retrieve and summarize the list of user playlists."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: information-retrieval
    tags: []
---
# Youtube Music Playlist Count Retrieval

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Ensure the necessary authentication configuration (e.g., `ytmusic_headers.json`) is present for API access.
2. Utilize the `ytmusicapi` integration to execute a request to retrieve the user's playlist data.
3. Parse the returned data to extract the playlist titles and associated track counts.
4. Calculate the total number of playlists based on the extracted list.