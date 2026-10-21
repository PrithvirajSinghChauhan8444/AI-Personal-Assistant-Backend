from typing import List, Optional
from langchain_core.tools import tool
from ..integrations import (
    get_user_playlists,
    create_user_playlist,
    add_tracks_to_playlist,
    search_ytmusic,
    run_script,
)

@tool
def ytmusic_list_playlists(auth_path: Optional[str] = None) -> str:
    """List YouTube Music library playlists."""
    res = get_user_playlists(auth_path=auth_path)
    return str(res)

@tool
def ytmusic_create_new_playlist(title: str, description: str = "", auth_path: Optional[str] = None) -> str:
    """Create a new playlist on YouTube Music."""
    res = create_user_playlist(title=title, description=description, auth_path=auth_path)
    return str(res)

@tool
def ytmusic_add_songs_to_playlist(playlist_id: str, video_ids: List[str], auth_path: Optional[str] = None) -> str:
    """Add song video IDs to a YouTube Music playlist."""
    res = add_tracks_to_playlist(playlist_id=playlist_id, video_ids=video_ids, auth_path=auth_path)
    return str(res)

@tool
def ytmusic_search_songs(query: str, filter_type: str = "songs") -> str:
    """Search for songs or artists on YouTube Music."""
    res = search_ytmusic(query=query, filter_type=filter_type)
    return str(res)

@tool
def execute_utility_script(script_path: str, args: Optional[List[str]] = None) -> str:
    """Execute a local Python utility script."""
    res = run_script(script_path=script_path, args=args)
    return str(res)

misc_tools = [
    ytmusic_list_playlists,
    ytmusic_create_new_playlist,
    ytmusic_add_songs_to_playlist,
    ytmusic_search_songs,
    execute_utility_script,
]
