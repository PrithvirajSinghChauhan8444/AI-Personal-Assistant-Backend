#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import json
# from dotenv import load_dotenv

# Find project root and load environment variables
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
# load_dotenv(os.path.join(project_root, ".env"), override=True)

# Add project root to python path to import spotipy client if available
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, "src"))

def run_dbus_cmd(method):
    """Run a D-Bus command to control Spotify on Linux."""
    try:
        cmd = [
            "dbus-send", "--print-reply", 
            "--dest=org.mpris.MediaPlayer2.spotify", 
            "/org/mpris/MediaPlayer2", 
            f"org.mpris.MediaPlayer2.Player.{method}"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            return True, res.stdout.strip()
        return False, res.stderr.strip()
    except Exception as e:
        return False, str(e)

def run_playerctl_cmd(action):
    """Run playerctl specifically targeted at Spotify."""
    try:
        cmd = ["playerctl", "-p", "spotify", action]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            return True, res.stdout.strip()
        return False, res.stderr.strip()
    except Exception as e:
        return False, str(e)

def get_dbus_metadata():
    """Retrieve metadata from Spotify via D-Bus."""
    try:
        # Get playback status
        cmd_status = [
            "dbus-send", "--print-reply", "--dest=org.mpris.MediaPlayer2.spotify",
            "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties.Get",
            "string:org.mpris.MediaPlayer2.Player", "string:PlaybackStatus"
        ]
        res_status = subprocess.run(cmd_status, capture_output=True, text=True, timeout=3)
        status = "Unknown"
        if res_status.returncode == 0:
            if "Playing" in res_status.stdout:
                status = "Playing"
            elif "Paused" in res_status.stdout:
                status = "Paused"
                
        # Get song details
        cmd_meta = [
            "dbus-send", "--print-reply", "--dest=org.mpris.MediaPlayer2.spotify",
            "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties.Get",
            "string:org.mpris.MediaPlayer2.Player", "string:Metadata"
        ]
        res_meta = subprocess.run(cmd_meta, capture_output=True, text=True, timeout=3)
        
        title = "Unknown Title"
        artist = "Unknown Artist"
        
        if res_meta.returncode == 0:
            # Parse title and artist from output lines
            stdout = res_meta.stdout
            
            import re
            # Find title
            title_match = re.search(r'string\s+"xesam:title"\s*\n\s*variant\s+string\s+"([^"]+)"', stdout)
            if title_match:
                title = title_match.group(1)
                
            # Find artist
            artist_match = re.search(r'string\s+"xesam:artist"\s*\n\s*variant\s+array\s+\[\s*\n\s*string\s+"([^"]+)"', stdout)
            if artist_match:
                artist = artist_match.group(1)
                
        return {
            "title": title,
            "artist": artist,
            "status": status,
            "source": "dbus"
        }
    except Exception as e:
        return {"error": str(e)}

def get_playerctl_metadata():
    """Retrieve metadata from Spotify via playerctl."""
    try:
        title_res = subprocess.run(["playerctl", "-p", "spotify", "metadata", "title"], capture_output=True, text=True, timeout=2)
        artist_res = subprocess.run(["playerctl", "-p", "spotify", "metadata", "artist"], capture_output=True, text=True, timeout=2)
        status_res = subprocess.run(["playerctl", "-p", "spotify", "status"], capture_output=True, text=True, timeout=2)
        
        if title_res.returncode == 0:
            return {
                "title": title_res.stdout.strip(),
                "artist": artist_res.stdout.strip() if artist_res.returncode == 0 else "Unknown Artist",
                "status": status_res.stdout.strip() if status_res.returncode == 0 else "Unknown Status",
                "source": "playerctl"
            }
        return None
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(description="Spotify Playback Controller (spotipy / D-Bus / playerctl)")
    parser.add_argument("action", choices=["play", "pause", "toggle", "next", "prev", "status"], help="Action to perform")
    args = parser.parse_args()

    # 1. Try Spotipy API if credentials exist
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    
    if client_id and client_secret and "YOUR_CLIENT" not in client_id:
        try:
            from Apps.Spotify import spotify_client
            if args.action == "status":
                song = spotify_client.get_current_song()
                if song and "title" in song:
                    print(json.dumps({
                        "title": song.get("title", "Unknown Title"),
                        "artist": song.get("artist", "Unknown Artist"),
                        "status": "Playing" if song.get("is_playing") else "Paused",
                        "progress": f"{song.get('progress_ms', 0) // 1000}s / {song.get('duration_ms', 0) // 1000}s",
                        "source": "api"
                    }))
                    return
                else:
                    raise Exception("No active track returned by API (possible free account/no premium subscription)")
            elif args.action == "play":
                res = spotify_client.play_pause() # play_pause handles both play and pause
                if res in ["Error", "No Active Device"]:
                    raise Exception(f"API play failed: {res}")
                # Make sure it's playing
                sp = spotify_client.get_spotify_client()
                if sp:
                    current = sp.current_playback()
                    if current and not current.get('is_playing'):
                        spotify_client.play_pause()
                print(json.dumps({"status": "command_sent", "action": "play", "source": "api"}))
                return
            elif args.action == "pause":
                res = spotify_client.play_pause()
                if res in ["Error", "No Active Device"]:
                    raise Exception(f"API pause failed: {res}")
                # Make sure it's paused
                sp = spotify_client.get_spotify_client()
                if sp:
                    current = sp.current_playback()
                    if current and current.get('is_playing'):
                        spotify_client.play_pause()
                print(json.dumps({"status": "command_sent", "action": "pause", "source": "api"}))
                return
            elif args.action == "toggle":
                res = spotify_client.play_pause()
                if res in ["Error", "No Active Device"]:
                    raise Exception(f"API toggle failed: {res}")
                print(json.dumps({"status": "command_sent", "action": "toggle", "result": res, "source": "api"}))
                return
            elif args.action == "next":
                res = spotify_client.next_track()
                if res in ["Error", "No Active Device"]:
                    raise Exception(f"API next failed: {res}")
                print(json.dumps({"status": "command_sent", "action": "next", "result": res, "source": "api"}))
                return
            elif args.action == "prev":
                res = spotify_client.previous_track()
                if res in ["Error", "No Active Device"]:
                    raise Exception(f"API prev failed: {res}")
                print(json.dumps({"status": "command_sent", "action": "prev", "result": res, "source": "api"}))
                return
        except Exception as api_err:
            # Fall back to local controls on API errors (like 403 Premium Required)
            pass
            
    # 2. Fallback to Local OS controls (playerctl / D-Bus)
    action_map_playerctl = {
        "play": "play",
        "pause": "pause",
        "toggle": "play-pause",
        "next": "next",
        "prev": "previous"
    }
    
    action_map_dbus = {
        "play": "Play",
        "pause": "Pause",
        "toggle": "PlayPause",
        "next": "Next",
        "prev": "Previous"
    }

    if args.action == "status":
        # Try playerctl first
        meta = get_playerctl_metadata()
        if not meta or "error" in meta:
            # Try D-Bus directly
            meta = get_dbus_metadata()
        print(json.dumps(meta))
    else:
        # Try playerctl
        success, err = run_playerctl_cmd(action_map_playerctl[args.action])
        if not success:
            # Try D-Bus direct
            success, err = run_dbus_cmd(action_map_dbus[args.action])
            
        if success:
            print(json.dumps({"status": "command_sent", "action": args.action, "source": "local_os"}))
        else:
            print(json.dumps({"error": f"Failed to control Spotify. OS Error: {err}. Spotipy keys not configured."}))

if __name__ == "__main__":
    main()
