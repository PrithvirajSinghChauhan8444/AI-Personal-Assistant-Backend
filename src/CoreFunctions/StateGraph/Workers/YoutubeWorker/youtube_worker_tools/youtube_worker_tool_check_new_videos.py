import json
from typing import List, Optional
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Google.youtube_ops import check_new_videos

def check_channel_new_videos(channel_ids: List[str], limit_per_channel: int = 4, hours_limit: Optional[int] = None, account: str = "personal") -> str:
    """Check for new, unseen videos uploaded by specific channels. Filters out videos already read or viewed.
    
    Args:
        channel_ids (list): List of YouTube channel IDs to check.
        limit_per_channel (int): Max number of latest videos to retrieve per channel. Defaults to 4.
        hours_limit (int, optional): Only include videos published within the last N hours. Defaults to None.
        account (str): The Google account to use. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: check_channel_new_videos")
    try:
        # Convert channel_ids to a list if passed as string
        if isinstance(channel_ids, str):
            try:
                channel_ids = json.loads(channel_ids)
            except Exception:
                channel_ids = [c.strip() for c in channel_ids.split(",") if c.strip()]
                
        videos = check_new_videos(
            channel_ids=channel_ids,
            limit_per_channel=limit_per_channel,
            hours_limit=hours_limit,
            account=account
        )
        if not videos:
            return "No new videos found for the specified channels."
        return json.dumps(videos, indent=2)
    except Exception as e:
        return f"Error checking new videos: {e}"

youtube_worker_tool_check_new_videos = StructuredTool.from_function(
    func=check_channel_new_videos,
    name="check_channel_new_videos",
    description="Check for new, unseen videos uploaded by a list of channel IDs. Automatically filters out videos already marked as read or viewed."
)
