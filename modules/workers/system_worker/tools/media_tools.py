from typing import Optional
from langchain_core.tools import tool
from modules.workers.system_worker.integrations.media_client import (
    control_spotify_playback,
    control_youtube_music_playback,
    control_system_media_playback
)

@tool
def control_spotify(action: str, volume: Optional[int] = None) -> str:
    """Controls Spotify playback, tracks, and volume.
    
    Args:
        action (str): Action to perform: 'play', 'pause', 'toggle', 'next', 'previous', 'status', 'volume'.
        volume (int, optional): Volume percentage (0-100) when action is 'volume'.
    """
    return control_spotify_playback(action=action, volume=volume)

@tool
def control_youtube_music(action: str, query: Optional[str] = None) -> str:
    """Controls YouTube Music browser playback, search, track switching, and status.
    
    Args:
        action (str): Action to perform: 'play', 'pause', 'toggle', 'next', 'previous', 'status', 'open', 'like'.
        query (str, optional): Search query or song title when searching or playing.
    """
    return control_youtube_music_playback(action=action, query=query)

@tool
def control_system_media(action: str) -> str:
    """Controls system media player playback (play-pause, next, previous) via D-Bus / playerctl.
    
    Args:
        action (str): Media action: 'play-pause', 'next', or 'previous'.
    """
    return control_system_media_playback(action=action)

media_tools = [control_spotify, control_youtube_music, control_system_media]
