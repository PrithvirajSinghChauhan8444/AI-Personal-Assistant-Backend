from src.CoreFunctions.StateGraph.registry import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.SystemWorker.system_prompt import SYSTEM_PROMPT
from src.CoreFunctions.StateGraph.Workers.SystemWorker.system_tools import system_tools

@WorkerRegistry.register
class SystemWorker(BaseWorker):
    name = "SystemWorker"
    description = "Handles OS terminal commands, file management, scripts, system health, and worker/agent configuration/listing. It is the ONLY worker with local file system write/read permissions."
    instructions = SYSTEM_PROMPT
    tools = system_tools
    categories = ["system-management", "system-monitoring", "system-automation", "SystemWorker"]

    @property
    def routing_rules(self) -> List[str]:
        return [
            "**Media Control / Music Playback Workflow**:\n   - Any requests to control playback (play, pause, toggle, next, previous, status check) for Spotify or YouTube Music should be routed to SystemWorker. SystemWorker must run the local helper python scripts using the project's virtual environment interpreter (e.g. `.venv/bin/python3 Skills/media-control/youtube-music-control/scripts/youtube_music_control.py` or `.venv/bin/python3 Skills/media-control/spotify-playback-control/scripts/spotify_playback_control.py`) to execute these actions. Do NOT use system `python3` or try to install packages.",
            "**Local File System Access & File Management**:\n   - Only SystemWorker has permission and tools to access the local file system. This includes creating/deleting directories, creating/updating files, downloading files to disk, reading file contents, listing folders/directories, and executing terminal commands.\n   - All other workers (BrowserWorker, GmailWorker, ClassroomWorker, GithubWorker, ProductivityWorker, MemoryWorker, MiscWorker) DO NOT have direct access to the local filesystem.\n   - If a request requires retrieving or generating data from any external source (e.g., scraping web contents, fetching Gmail attachments, downloading Classroom materials) and saving/downloading that content to the local disk, you MUST split it into sequential subtasks:\n     - The first task (assigned to the retrieving worker, e.g., BrowserWorker, GmailWorker, ClassroomWorker, etc.): Retrieve/fetch the data or content.\n     - The second task (assigned to SystemWorker, which MUST depend on the first task): Write/save that content, create local directories, or download the files to the local file system using the retrieved data.\n   - If a request requires accessing or reading a local file to process it with another worker, you MUST split it into:\n     - The first task (assigned to SystemWorker): Read the file contents from the local file system.\n     - The second task (assigned to the processing worker, e.g., GmailWorker, BrowserWorker, etc., depending on the SystemWorker read task): Process the read content."
        ]
