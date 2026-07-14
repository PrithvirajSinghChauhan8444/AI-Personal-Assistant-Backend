import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Google.youtube_ops import search_youtube_videos

def search_videos(query: str, max_results: int = 5, account: str = "personal") -> str:
    """Search for YouTube videos matching a query.
    
    Args:
        query (str): The search terms or query (e.g., 'python advanced topics', 'productivity guides').
        max_results (int): Maximum number of search results to return. Defaults to 5.
        account (str): The Google account to use. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: search_videos")
    try:
        results = search_youtube_videos(query, max_results=max_results, account=account)
        if not results:
            return "No videos found matching the query."
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error searching videos: {e}"

youtube_worker_tool_search_videos = StructuredTool.from_function(
    func=search_videos,
    name="search_videos",
    description="Search for YouTube videos by keywords, returning titles, video IDs, descriptions, and channel details."
)
