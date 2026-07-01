from src.CoreFunctions.StateGraph.registry import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.MemoryWorker.memory_prompt import SYSTEM_PROMPT
from src.CoreFunctions.StateGraph.Workers.MemoryWorker.memory_worker_tools import memory_tools

@WorkerRegistry.register
class MemoryWorker(BaseWorker):
    name = "MemoryWorker"
    description = "Long-term memory storage and retrieval."
    instructions = SYSTEM_PROMPT
    tools = memory_tools
    categories = ["productivity", "MemoryWorker"]
    use_local_llm = True
