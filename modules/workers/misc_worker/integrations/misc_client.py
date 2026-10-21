import os
import json
import subprocess
from typing import Dict, Any, List, Optional

AUTH_PATHS = [
    "config/ytmusic_headers.json",
    "headers_auth.json",
    os.path.expanduser("~/.config/ytmusicapi/headers_auth.json")
]

def _get_ytmusic_client():
    try:
        from ytmusicapi import YTMusic
        for path in AUTH_PATHS:
            if os.path.exists(path):
                return YTMusic(path)
        return YTMusic()
    except Exception as e:
        return None

def get_user_playlists(auth_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve user playlists from YouTube Music."""
    try:
        from ytmusicapi import YTMusic
        client = None
        if auth_path and os.path.exists(auth_path):
            client = YTMusic(auth_path)
        else:
            client = _get_ytmusic_client()

        if not client:
            return [{"error": "ytmusicapi not installed or unavailable."}]

        playlists = client.get_library_playlists()
        return playlists if isinstance(playlists, list) else []
    except Exception as e:
        return [{"error": f"Failed to retrieve playlists: {str(e)}"}]

def create_user_playlist(title: str, description: str = "", auth_path: Optional[str] = None) -> Dict[str, Any]:
    """Create a new playlist on YouTube Music."""
    try:
        from ytmusicapi import YTMusic
        client = None
        if auth_path and os.path.exists(auth_path):
            client = YTMusic(auth_path)
        else:
            client = _get_ytmusic_client()

        if not client:
            return {"error": "ytmusicapi not installed or unavailable."}

        playlist_id = client.create_playlist(title, description)
        return {"status": "success", "playlist_id": playlist_id, "title": title}
    except Exception as e:
        return {"error": f"Failed to create playlist: {str(e)}"}

def add_tracks_to_playlist(playlist_id: str, video_ids: List[str], auth_path: Optional[str] = None) -> Dict[str, Any]:
    """Add tracks to an existing playlist on YouTube Music."""
    try:
        from ytmusicapi import YTMusic
        client = None
        if auth_path and os.path.exists(auth_path):
            client = YTMusic(auth_path)
        else:
            client = _get_ytmusic_client()

        if not client:
            return {"error": "ytmusicapi not installed or unavailable."}

        res = client.add_playlist_items(playlist_id, video_ids)
        return {"status": "success", "result": res}
    except Exception as e:
        return {"error": f"Failed to add tracks: {str(e)}"}

def search_ytmusic(query: str, filter_type: str = "songs") -> List[Dict[str, Any]]:
    """Search YouTube Music for songs, artists, or albums."""
    try:
        from ytmusicapi import YTMusic
        client = _get_ytmusic_client()
        if not client:
            return [{"error": "ytmusicapi not installed or unavailable."}]
        results = client.search(query, filter=filter_type)
        return results[:10] if isinstance(results, list) else []
    except Exception as e:
        return [{"error": f"Failed to search music: {str(e)}"}]

def run_script(script_path: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
    """Execute a local automation/utility script safely."""
    if not os.path.exists(script_path):
        return {"error": f"Script not found: {script_path}"}
    cmd = ["python3", script_path] + (args or [])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            "status": "success" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except Exception as e:
        return {"error": f"Script execution failed: {str(e)}"}
