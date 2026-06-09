---
name: youtube-music-control
description: "Control playback and search for tracks on YouTube Music directly via the browser."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: media-control
    tags: [music, playback, media, youtube]
---
# YouTube Music Playback Control

## When to Use
Use this skill when you need to play, pause, skip, go back, query status, or search and play music on YouTube Music.

## Procedure
1. Execute the helper script `youtube_music_control.py` located under `Skills/media-control/youtube-music-control/scripts/youtube_music_control.py` with python3.
2. Supported commands/arguments:
   - `status`: Retrieve current playing track title, artist, progress, and status (Playing/Paused).
   - `play`: Resume playback.
   - `pause`: Pause playback.
   - `toggle`: Toggle between play and pause.
   - `next`: Play the next track.
   - `prev`: Play the previous track.
   - `search --query "<song name>"`: Search for a song or playlist and play the first result.
3. Present the JSON output of the command in a clean, human-readable format.
