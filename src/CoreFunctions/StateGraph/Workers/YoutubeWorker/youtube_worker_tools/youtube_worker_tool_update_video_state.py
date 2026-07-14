from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Google.youtube_ops import set_video_state

def update_video_state(video_id: str, state: str) -> str:
    """Mark a YouTube video as 'read' or 'viewed' in the local database.
    
    Args:
        video_id (str): The unique 11-character YouTube video ID.
        state (str): The status to set. Must be either 'read' (summarized) or 'viewed' (watched/clicked).
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: update_video_state")
    try:
        if state not in ["read", "viewed"]:
            return "Error: state must be either 'read' or 'viewed'."
        set_video_state(video_id, state)
        return f"Video ID '{video_id}' successfully marked as '{state}' in local database."
    except Exception as e:
        return f"Error updating video state: {e}"

youtube_worker_tool_update_video_state = StructuredTool.from_function(
    func=update_video_state,
    name="update_video_state",
    description="Mark a YouTube video as 'read' (summarized) or 'viewed' (watched/clicked) in the local database. This filters it out of future check alerts."
)
