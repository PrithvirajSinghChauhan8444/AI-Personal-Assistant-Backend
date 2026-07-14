from typing import List
from src.CoreFunctions.StateGraph.worker_framework import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.YoutubeWorker.youtube_prompt import SYSTEM_PROMPT
from src.CoreFunctions.StateGraph.Workers.YoutubeWorker.youtube_worker_tools import youtube_tools

@WorkerRegistry.register
class YoutubeWorker(BaseWorker):
    name = "YoutubeWorker"
    description = "Interacts with YouTube: fetches subscription updates, searches for relevant videos, transcribes videos for detailed summaries, and tracks read/viewed video states."
    instructions = SYSTEM_PROMPT
    tools = youtube_tools
    categories = ["youtube", "information-retrieval", "YoutubeWorker"]

    @property
    def routing_rules(self) -> List[str]:
        return [
            "**YouTube Interaction & Video Analysis Workflow**:\n"
            "   - Any requests related to YouTube (e.g., searching for videos, checking for updates on subscribed channels, transcribing videos, summarizing videos, or marking a video as read or viewed) MUST be routed to YoutubeWorker."
        ]
