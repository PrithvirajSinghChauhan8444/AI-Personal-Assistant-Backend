import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv
load_dotenv() # This loads the variables from .env

# --- CONFIGURATION (Paste your keys here) ---
client_id= os.getenv("SPOTIPY_CLIENT_ID")
client_secret= os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = 'http://127.0.0.1:8888/callback'

# Scope: Read status + Control playback
SCOPE = "user-read-playback-state,user-modify-playback-state"

def get_spotify_client():
    """
    Authenticates with Spotify.
    First run: Opens browser to login.
    Next runs: Uses cached token.
    """
    try:
        # Check if keys are actually set
        if 'YOUR_CLIENT' in client_id:
            print("⚠️ Spotify keys not set yet.")
            return None

        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            scope=SCOPE,
            cache_path=".spotify_cache", # Saves login locally
            open_browser=True
        ))
        return sp
    except Exception as e:
        print(f"❌ Spotify Auth Error: {e}")
        return None

def get_current_song():
    """
    Fetches the currently playing song.
    If nothing is playing, fetches the LAST played song so the UI isn't empty.
    """
    sp = get_spotify_client()
    if not sp:
        return None

    try:
        # 1. Try to get 'Current Playback' (Active session)
        current = sp.current_playback()

        if current and current.get('item'):
            track = current['item']
            return {
                "is_playing": current['is_playing'],
                "title": track['name'],
                "artist": track['artists'][0]['name'],
                "album_art": track['album']['images'][0]['url'],
                "progress_ms": current['progress_ms'],
                "duration_ms": track['duration_ms']
            }

        # 2. If nothing is active, get 'Recently Played' (History)
        # This fixes the "Empty UI" when paused
        recent = sp.current_user_recently_played(limit=1)
        if recent and recent['items']:
            track = recent['items'][0]['track']
            return {
                "is_playing": False, # We know it's paused
                "title": track['name'],
                "artist": track['artists'][0]['name'],
                "album_art": track['album']['images'][0]['url'],
                "progress_ms": 0,
                "duration_ms": track['duration_ms']
            }

        return {"is_playing": False}

    except Exception as e:
        print(f"⚠️ Spotify Error: {e}")
        return {"is_playing": False}
# --- CONTROLS ---

def play_pause():
    sp = get_spotify_client()
    if not sp: return "Error"
    
    current = sp.current_playback()
    if current and current.get('is_playing'):
        sp.pause_playback()
        return "Paused"
    else:
        # Resume playback (might fail if no active device)
        try:
            sp.start_playback()
            return "Playing"
        except:
            return "No Active Device"

def next_track():
    sp = get_spotify_client()
    if sp: sp.next_track()
    return "Skipped"

def previous_track():
    sp = get_spotify_client()
    if sp: sp.previous_track()
    return "Previous"
