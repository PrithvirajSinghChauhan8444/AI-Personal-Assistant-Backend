from src.CoreFunctions.StateGraph.registry import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_prompt import SYSTEM_PROMPT
from src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_worker_tools import gmail_tools

@WorkerRegistry.register
class GmailWorker(BaseWorker):
    name = "GmailWorker"
    description = "Reads, searches, and sends emails."
    instructions = SYSTEM_PROMPT
    tools = gmail_tools
    categories = ["communication", "GmailWorker"]
