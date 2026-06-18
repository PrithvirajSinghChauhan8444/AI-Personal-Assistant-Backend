from src.CoreFunctions.StateGraph.registry import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.MiscWorker.misc_prompt import SYSTEM_PROMPT
from src.CoreFunctions.StateGraph.Workers.MiscWorker.misc_tools import misc_tools

@WorkerRegistry.register
class MiscWorker(BaseWorker):
    name = "MiscWorker"
    description = "General-purpose worker for miscellaneous integrations, calculations, custom scripts."
    instructions = SYSTEM_PROMPT
    tools = misc_tools
    categories = ["general", "misc", "MiscWorker"]

    @property
    def routing_rules(self) -> List[str]:
        return [
            "**Miscellaneous API & Playlist Management**:\n   - Any requests to manage playlists (creating, adding songs, removing songs, listing library/favorite songs) on YouTube Music or other APIs should be routed to MiscWorker. MiscWorker can run custom background API scripts or libraries (like `ytmusicapi`) to complete these commands instantly."
        ]
