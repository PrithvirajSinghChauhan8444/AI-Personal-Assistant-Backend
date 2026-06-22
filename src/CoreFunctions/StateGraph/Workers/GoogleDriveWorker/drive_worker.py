from src.CoreFunctions.StateGraph.registry import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.GoogleDriveWorker.drive_prompt import SYSTEM_PROMPT
from src.CoreFunctions.StateGraph.Workers.GoogleDriveWorker.drive_tools import drive_tools

@WorkerRegistry.register
class GoogleDriveWorker(BaseWorker):
    name = "GoogleDriveWorker"
    description = "Manages files on Google Drive (list, search, download, upload, create folder, delete)."
    instructions = SYSTEM_PROMPT
    tools = drive_tools
    categories = ["cloud-storage", "GoogleDriveWorker"]
