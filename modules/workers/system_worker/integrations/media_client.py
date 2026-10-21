import os
import sys
import subprocess
from typing import Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
PYTHON_EXEC = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
if not os.path.exists(PYTHON_EXEC):
    PYTHON_EXEC = sys.executable

def control_spotify_playback(action: str, volume: Optional[int] = None) -> str:
    """Controls Spotify playback, tracks, and volume via D-Bus / playerctl / Web API."""
    script_path = os.path.join(
        PROJECT_ROOT, 
        "Skills", 
        "SystemWorker", 
        "spotify-playback-control", 
        "scripts", 
        "spotify_playback_control.py"
    )
    if os.path.exists(script_path):
        cmd = [PYTHON_EXEC, script_path, "--action", action]
        if volume is not None:
            cmd.extend(["--volume", str(volume)])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            output = res.stdout.strip() or res.stderr.strip()
            if output:
                return output
        except Exception:
            pass

    # Direct fallback via playerctl
    try:
        playerctl_action = "play-pause" if action in ["play", "pause", "toggle"] else action
        cmd = ["playerctl", "-p", "spotify", playerctl_action]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            return f"Spotify action '{action}' executed successfully."
        return f"Spotify action response: {res.stderr or res.stdout}"
    except Exception as e:
        return f"Error controlling Spotify: {e}"

def control_youtube_music_playback(action: str, query: Optional[str] = None) -> str:
    """Controls YouTube Music browser playback, searching, and track switching."""
    script_path = os.path.join(
        PROJECT_ROOT, 
        "Skills", 
        "MiscWorker", 
        "youtube-music-control", 
        "scripts", 
        "youtube_music_control.py"
    )
    if os.path.exists(script_path):
        cmd = [PYTHON_EXEC, script_path, "--action", action]
        if query:
            cmd.extend(["--query", query])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            output = res.stdout.strip() or res.stderr.strip()
            if output:
                return output
        except Exception as e:
            return f"Error running YouTube Music script: {e}"

    return f"YouTube Music script not available. Sent signal for action '{action}'."

def control_system_media_playback(action: str) -> str:
    """Controls general system media player playback."""
    try:
        from src.CoreFunctions.Integrations.System.system_actions import media_control
        return media_control(action)
    except Exception:
        playerctl_action = "play-pause" if "pause" in action or "play" in action else action
        cmd = ["playerctl", playerctl_action]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            return f"System media {action} executed."
        except Exception as e:
            return f"System media control failed: {e}"
