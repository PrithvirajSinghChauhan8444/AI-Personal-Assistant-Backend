import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Google.youtube_ops import get_video_details

def fetch_youtube_video_details(video_id: str, account: str = "personal") -> str:
    """Fetch metadata and snippet details (title, description, channel, tags) of a specific YouTube video.
    This is useful for getting a quick description or preview of a video without transcribing the entire content.
    
    Args:
        video_id (str): The unique 11-character YouTube video ID.
        account (str): The Google account to use. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_youtube_video_details")
    try:
        details = get_video_details(video_id, account=account)
        if not details:
            return f"No video details found for video ID '{video_id}'."
        return json.dumps(details, indent=2)
    except Exception as e:
        return f"Error fetching video details: {e}"

youtube_worker_tool_get_video_details = StructuredTool.from_function(
    func=fetch_youtube_video_details,
    name="fetch_youtube_video_details",
    description="Fetch details (title, description, channel, tags) of a specific YouTube video ID. Ideal for a quick preview or description."
)
