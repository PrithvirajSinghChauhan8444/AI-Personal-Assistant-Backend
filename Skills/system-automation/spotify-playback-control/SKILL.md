---
name: spotify-playback-control
description: "A generalized procedure for controlling Spotify playback via a local script, involving launching the application and sending specific commands."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: system-automation
    tags: []
---
# Spotify Playback Control

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Execute the dedicated Python script located at `/home/prit/Project_Linux/AI-Personal-Assistant-Backend/Skills/media-control/spotify-playback_control/scripts/spotify_playback_control.py` to initiate playback commands.
2. Ensure the Spotify application is launched using the system command `/usr/bin/spotify` to establish the necessary process context.
3. The script execution confirms the successful transmission of the command and the resulting process ID (PID) for tracking.