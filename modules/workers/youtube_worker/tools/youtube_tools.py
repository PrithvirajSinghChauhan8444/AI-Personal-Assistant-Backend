from typing import Optional, List
from langchain_core.tools import tool
from modules.workers.youtube_worker.integrations.youtube_client import (
    search_videos as _search_videos,
    get_video_details as _get_details,
    list_subscriptions as _list_subs,
    check_new_videos as _check_new,
    transcribe_video as _transcribe,
    update_video_state as _update_state,
    get_channel_details as _get_chan
)

@tool
def search_youtube_videos(query: str, max_results: int = 5, account: str = "personal") -> str:
    """Searches YouTube for videos matching a query."""
    res = _search_videos(query=query, max_results=max_results, account=account)
    items = res.get("videos", [])
    if not items:
        return f"No YouTube videos found matching '{query}'."
    lines = [f"Found {len(items)} videos:"]
    for v in items:
        vid_id = v.get("id") or v.get("videoId")
        lines.append(f"- [{v.get('title')}](<url>https://youtube.com/watch?v={vid_id}</url>) | Channel: {v.get('channelTitle')}")
    return "\n".join(lines)

@tool
def fetch_youtube_video_details(video_id: str, account: str = "personal") -> str:
    """Fetches title, description, and statistics of a YouTube video."""
    return str(_get_details(video_id=video_id, account=account))

@tool
def transcribe_youtube_video(video_id: str) -> str:
    """Fetches the complete English text transcript of a YouTube video."""
    res = _transcribe(video_id=video_id)
    if "error" in res:
        return f"Transcription error: {res['error']}"
    return res.get("transcript", "No transcript text available.")

@tool
def fetch_youtube_subscriptions(max_results: int = 25, account: str = "personal") -> str:
    """Lists the user's subscribed YouTube channels."""
    return str(_list_subs(max_results=max_results, account=account))

@tool
def check_channel_new_videos(channel_ids: List[str], hours_limit: int = 24, account: str = "personal") -> str:
    """Checks for newly uploaded videos across channels within the last hours_limit hours."""
    return str(_check_new(channel_ids=channel_ids, hours_limit=hours_limit, account=account))

@tool
def update_video_state_tool(video_id: str, state: str) -> str:
    """Updates the state of a YouTube video ('read' or 'viewed')."""
    return str(_update_state(video_id=video_id, state=state))

youtube_tools = [
    search_youtube_videos,
    fetch_youtube_video_details,
    transcribe_youtube_video,
    fetch_youtube_subscriptions,
    check_channel_new_videos,
    update_video_state_tool
]
