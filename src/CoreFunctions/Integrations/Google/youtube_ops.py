import os
import json
import re
from datetime import datetime, timezone
from googleapiclient.discovery import build
from src.CoreFunctions.Infrastructure.auth_utils import get_valid_credentials
from src.CoreFunctions.Infrastructure.MemoryLayer import MemoryManager
from src.CoreFunctions.Infrastructure.MemoryLayer import store_memory, fetch_memory, delete_memory
from youtube_transcript_api import YouTubeTranscriptApi

def get_youtube_service(account: str = "personal"):
    """Instantiates the authorized Google API client for YouTube.
    """
    try:
        creds = get_valid_credentials(account)
        if not creds:
            print("⚠️ [YouTube API] Could not get valid credentials.")
            return None
        return build('youtube', 'v3', credentials=creds)
    except Exception as e:
        print(f"⚠️ [YouTube API] Failed to initialize YouTube service: {e}")
        return None

def get_channel_details(account: str = "personal"):
    """Fetches details about the user's channel.
    """
    service = get_youtube_service(account)
    if not service:
        return {"error": "Authentication failed or service not available."}
    
    try:
        response = service.channels().list(
            mine=True,
            part="snippet,contentDetails,statistics"
        ).execute()
        
        items = response.get("items", [])
        if not items:
            return {"message": "No channel found for this account."}
        
        channel = items[0]
        snippet = channel.get("snippet", {})
        statistics = channel.get("statistics", {})
        
        return {
            "channel_id": channel.get("id"),
            "title": snippet.get("title"),
            "description": snippet.get("description"),
            "custom_url": snippet.get("customUrl"),
            "published_at": snippet.get("publishedAt"),
            "view_count": statistics.get("viewCount"),
            "subscriber_count": statistics.get("subscriberCount"),
            "video_count": statistics.get("videoCount")
        }
    except Exception as e:
        print(f"⚠️ [YouTube API] Error fetching channel details: {e}")
        return {"error": str(e)}

def list_subscribed_channels(account: str = "personal"):
    """Retrieves all channels the user is subscribed to.
    """
    service = get_youtube_service(account)
    if not service:
        return []
    
    subscriptions = []
    try:
        next_page_token = None
        while True:
            response = service.subscriptions().list(
                mine=True,
                part="snippet",
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                resource = snippet.get("resourceId", {})
                subscriptions.append({
                    "subscription_id": item.get("id"),
                    "channel_id": resource.get("channelId"),
                    "title": snippet.get("title"),
                    "description": snippet.get("description"),
                    "published_at": snippet.get("publishedAt")
                })
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
                
        return subscriptions
    except Exception as e:
        print(f"⚠️ [YouTube API] Error listing subscriptions: {e}")
        return []

def get_video_state(video_id: str) -> str:
    """Queries the local database for the video state ('read', 'viewed', or None).
    """
    try:
        val = fetch_memory(category="past", key=f"yt_state_{video_id}")
        return val if val else None
    except Exception as e:
        print(f"⚠️ [YouTube DB] Error reading video state: {e}")
        return None

def set_video_state(video_id: str, state: str):
    """Updates the video state to 'read' or 'viewed' in MemoryManager,
    enforcing a 500-item history limit.
    """
    if state not in ["read", "viewed"]:
        raise ValueError("State must be either 'read' or 'viewed'")
        
    try:
        # 1. Save the new state
        store_memory(category="past", key=f"yt_state_{video_id}", value=state)
        
        # 2. Enforce the 500-item history limit
        um = MemoryManager()
        if um.enabled:
            keys = um.list_keys("past:yt_state_*")
            if len(keys) > 500:
                print(f"🧹 [YouTube DB] Cleaning up old video states. Total keys: {len(keys)}")
                # Retrieve payload for all matching keys
                records = []
                for k in keys:
                    payload = um.retrieve_memory(k)
                    if payload and "timestamp" in payload:
                        # Extract the key name from database prefix (past:yt_state_...)
                        key_name = k.split(":", 1)[1]
                        records.append((key_name, payload["timestamp"]))
                
                # Sort records by timestamp (oldest first)
                records.sort(key=lambda x: x[1])
                
                # Delete oldest keys to drop back below 500
                delete_count = len(keys) - 500
                for i in range(delete_count):
                    old_key = records[i][0]
                    delete_memory("past", old_key)
                    
    except Exception as e:
        print(f"⚠️ [YouTube DB] Error writing video state: {e}")

def check_new_videos(channel_ids: list, limit_per_channel: int = 4, hours_limit: int = None, account: str = "personal"):
    """Scans channel uploads, checks against local database, and returns new videos.
    """
    service = get_youtube_service(account)
    if not service:
        return []
    
    new_videos = []
    now = datetime.now(timezone.utc)
    
    for channel_id in channel_ids:
        try:
            # 1. Get the uploads playlist ID
            chan_resp = service.channels().list(
                id=channel_id,
                part="contentDetails,snippet"
            ).execute()
            
            chan_items = chan_resp.get("items", [])
            if not chan_items:
                continue
                
            channel_title = chan_items[0]["snippet"]["title"]
            uploads_playlist_id = chan_items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
            
            # 2. Get latest videos from that playlist
            playlist_resp = service.playlistItems().list(
                playlistId=uploads_playlist_id,
                part="snippet",
                maxResults=limit_per_channel
            ).execute()
            
            for item in playlist_resp.get("items", []):
                snippet = item.get("snippet", {})
                video_id = snippet.get("resourceId", {}).get("videoId")
                
                if not video_id:
                    continue
                
                # Check local database: Skip if already marked read or viewed
                state = get_video_state(video_id)
                if state in ["read", "viewed"]:
                    continue
                
                published_at_str = snippet.get("publishedAt")
                # Parse publishedAt timestamp (e.g. '2026-07-14T05:30:00Z')
                published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                
                # Apply timeframe check if hours_limit is provided
                if hours_limit is not None:
                    delta = now - published_at
                    if (delta.total_seconds() / 3600.0) > hours_limit:
                        continue
                
                new_videos.append({
                    "video_id": video_id,
                    "title": snippet.get("title"),
                    "description": snippet.get("description"),
                    "published_at": published_at_str,
                    "channel_id": channel_id,
                    "channel_title": channel_title,
                    "link": f"https://youtube.com/watch?v={video_id}"
                })
        except Exception as e:
            print(f"⚠️ [YouTube API] Error checking channel '{channel_id}': {e}")
            continue
            
    return new_videos

def search_youtube_videos(query: str, max_results: int = 5, account: str = "personal"):
    """Performs standard YouTube search queries.
    """
    service = get_youtube_service(account)
    if not service:
        return []
    
    try:
        response = service.search().list(
            q=query,
            part="snippet",
            maxResults=max_results,
            type="video"
        ).execute()
        
        videos = []
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId")
            
            if not video_id:
                continue
                
            videos.append({
                "video_id": video_id,
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "published_at": snippet.get("publishedAt"),
                "channel_id": snippet.get("channelId"),
                "channel_title": snippet.get("channelTitle"),
                "link": f"https://youtube.com/watch?v={video_id}",
                "state": get_video_state(video_id)
            })
            
        return videos
    except Exception as e:
        print(f"⚠️ [YouTube API] Error searching videos: {e}")
        return []

def get_video_transcript(video_id: str):
    """Retrieves full transcript lines for a specific video ID.
    """
    try:
        api = YouTubeTranscriptApi()
        try:
            # Try common languages first
            transcript_list = api.fetch(video_id, languages=["en", "hi", "es", "fr", "de"])
        except Exception:
            # Fallback: get the first available transcript list item and fetch it
            transcripts = api.list(video_id)
            first_transcript = next(iter(transcripts))
            transcript_list = first_transcript.fetch()
        
        merged_text = []
        for line in transcript_list:
            text = line.get("text", "").strip()
            start = line.get("start", 0)
            # Format time as MM:SS
            minutes = int(start // 60)
            seconds = int(start % 60)
            timestamp_str = f"[{minutes:02d}:{seconds:02d}]"
            merged_text.append(f"{timestamp_str} {text}")
            
        return "\n".join(merged_text)
    except Exception as e:
        print(f"⚠️ [YouTube Transcript] Transcript fetch failed for '{video_id}': {e}")
        return f"Error: No transcript or captions found for video ID '{video_id}' ({e})."

def get_video_details(video_id: str, account: str = "personal"):
    """Fetches metadata details (title, description, channel, tags) of a specific video ID.
    """
    service = get_youtube_service(account)
    if not service:
        return None
    try:
        response = service.videos().list(
            id=video_id,
            part="snippet"
        ).execute()
        items = response.get("items", [])
        if not items:
            return None
        video = items[0]
        snippet = video.get("snippet", {})
        return {
            "video_id": video_id,
            "title": snippet.get("title"),
            "description": snippet.get("description"),
            "channel_title": snippet.get("channelTitle"),
            "tags": snippet.get("tags", []),
            "published_at": snippet.get("publishedAt"),
            "link": f"https://youtube.com/watch?v={video_id}"
        }
    except Exception as e:
        print(f"⚠️ [YouTube API] Error fetching video details for '{video_id}': {e}")
        return None
