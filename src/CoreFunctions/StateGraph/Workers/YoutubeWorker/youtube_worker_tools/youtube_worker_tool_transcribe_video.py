from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Google.youtube_ops import get_video_transcript

def transcribe_youtube_video(video_id: str) -> str:
    """Fetch the full transcript (captions) of a YouTube video.
    
    Args:
        video_id (str): The unique 11-character YouTube video ID (e.g., 'dQw4w9WgXcQ' from the URL 'https://youtube.com/watch?v=dQw4w9WgXcQ').
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: transcribe_youtube_video")
    try:
        transcript = get_video_transcript(video_id)
        return transcript
    except Exception as e:
        return f"Error transcribing video: {e}"

youtube_worker_tool_transcribe_video = StructuredTool.from_function(
    func=transcribe_youtube_video,
    name="transcribe_youtube_video",
    description="Fetch the full transcript (captions) of a YouTube video by its video ID. Useful for analyzing or summarizing a video."
)
