import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Google.youtube_ops import get_channel_details

def fetch_youtube_channel_details(account: str = "personal") -> str:
    """Fetch details about your own YouTube channel (channel ID, subscriber count, views, description).
    
    Args:
        account (str): The Google account to use (e.g., 'personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_youtube_channel_details")
    try:
        details = get_channel_details(account=account)
        return json.dumps(details, indent=2)
    except Exception as e:
        return f"Error fetching channel details: {e}"

youtube_worker_tool_get_channel_details = StructuredTool.from_function(
    func=fetch_youtube_channel_details,
    name="fetch_youtube_channel_details",
    description="Fetch details about your own YouTube channel including subscriber count, description, and channel ID."
)
