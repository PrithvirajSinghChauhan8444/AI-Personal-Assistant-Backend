---
name: spotify-playback-control
description: "Controls the playback state (play/pause) of the currently running Spotify application."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: Application Control
    tags: []
---
# Spotify Playback Control

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Detect the running Spotify application instance. 2. Send the `play-pause` command to the system media controller associated with that instance. 3. The system executes the command, toggling the playback state for the active Spotify session.