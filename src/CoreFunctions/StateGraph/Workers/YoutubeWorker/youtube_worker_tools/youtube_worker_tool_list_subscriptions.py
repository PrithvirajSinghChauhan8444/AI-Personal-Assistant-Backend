import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Google.youtube_ops import list_subscribed_channels

def fetch_youtube_subscriptions(account: str = "personal") -> str:
    """List the YouTube channels you are subscribed to.
    
    Args:
        account (str): The Google account to use (e.g., 'personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_youtube_subscriptions")
    try:
        subs = list_subscribed_channels(account=account)
        if not subs:
            return "No subscribed channels found or failed to retrieve subscriptions."
        return json.dumps(subs, indent=2)
    except Exception as e:
        return f"Error listing subscriptions: {e}"

youtube_worker_tool_list_subscriptions = StructuredTool.from_function(
    func=fetch_youtube_subscriptions,
    name="fetch_youtube_subscriptions",
    description="List all the YouTube channels you are subscribed to, returning channel titles and channel IDs."
)
