---
name: spotify-playback-control
description: "A generalized procedure for retrieving the current playback status (title, artist, status) from Spotify using external tools like `playerctl`."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: media-control
    tags: []
---
# Spotify Playback Control

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Identify the desired playback status (e.g., 'playing', 'paused').
2. Execute the specialized script located at `/home/prit/Project_Linux/AI-Personal-Assistant-Backend/Skills/media-control/spotify-playback-control/scripts/spotify_playback_control.py`, passing the appropriate argument (e.g., `status`).
3. Parse the output to extract the song title, artist, and current status.