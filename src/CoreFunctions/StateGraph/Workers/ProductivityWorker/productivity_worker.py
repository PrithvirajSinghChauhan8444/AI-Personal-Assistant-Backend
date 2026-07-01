from src.CoreFunctions.StateGraph.registry import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.ProductivityWorker.productivity_prompt import SYSTEM_PROMPT
from src.CoreFunctions.StateGraph.Workers.ProductivityWorker.productivity_worker_tools import calendar_tools

@WorkerRegistry.register
class ProductivityWorker(BaseWorker):
    name = "ProductivityWorker"
    description = "Calendar events, Google Tasks, Weather."
    instructions = SYSTEM_PROMPT
    tools = calendar_tools
    categories = ["productivity", "ProductivityWorker"]
