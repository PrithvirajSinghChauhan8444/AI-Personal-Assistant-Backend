"""System diagnostics, OS control, and media playback integrations for system_worker."""
from .media_client import (
    control_spotify_playback,
    control_youtube_music_playback,
    control_system_media_playback
)
from .system_client import (
    get_cpu_and_memory_health,
    read_local_file,
    write_local_file,
    list_local_directory,
    copy_clipboard_text,
    paste_clipboard_text,
    get_running_processes,
    launch_desktop_app,
    set_audio_volume
)

__all__ = [
    "control_spotify_playback",
    "control_youtube_music_playback",
    "control_system_media_playback",
    "get_cpu_and_memory_health",
    "read_local_file",
    "write_local_file",
    "list_local_directory",
    "copy_clipboard_text",
    "paste_clipboard_text",
    "get_running_processes",
    "launch_desktop_app",
    "set_audio_volume"
]
