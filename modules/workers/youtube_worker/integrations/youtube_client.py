from typing import Dict, Any, List, Optional
from googleapiclient.discovery import build
from modules.infrastructure.security.oauth import get_google_credentials
from src.CoreFunctions.Integrations.Google.youtube_ops import (
    get_channel_details as _get_channel_details,
    list_subscribed_channels as _list_subscribed_channels,
    search_youtube_videos as _search_youtube_videos,
    get_video_details as _get_video_details,
    check_new_videos as _check_new_videos,
    get_video_transcript as _get_video_transcript,
    set_video_state as _set_video_state
)

def get_youtube_service(account: str = "personal"):
    """Instantiates the authorized Google API client for YouTube."""
    creds = get_google_credentials(account)
    if not creds:
        return None
    return build('youtube', 'v3', credentials=creds)

def get_channel_details(account: str = "personal") -> dict:
    return _get_channel_details(account=account)

def list_subscriptions(account: str = "personal") -> dict:
    return _list_subscribed_channels(account=account)

def search_videos(query: str, max_results: int = 5, account: str = "personal") -> dict:
    return _search_youtube_videos(query=query, max_results=max_results, account=account)

def get_video_details(video_id: str, account: str = "personal") -> dict:
    return _get_video_details(video_id=video_id, account=account)

def check_new_videos(channel_ids: list, limit_per_channel: int = 4, hours_limit: Optional[int] = 24, account: str = "personal") -> dict:
    return _check_new_videos(channel_ids=channel_ids, limit_per_channel=limit_per_channel, hours_limit=hours_limit, account=account)

def transcribe_video(video_id: str) -> dict:
    return _get_video_transcript(video_id=video_id)

def update_video_state(video_id: str, state: str) -> dict:
    return _set_video_state(video_id=video_id, state=state)
