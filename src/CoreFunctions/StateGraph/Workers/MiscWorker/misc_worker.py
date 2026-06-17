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
