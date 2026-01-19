from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import memory_tools

def create_memory_worker(model):
    """
    Creates the MemoryWorker node.
    """
    system_prompt = (
        "You are the MemoryWorker. "
        "Your role is to manage long-term memory for the assistant. "
        "Use 'remember' to store important user details, preferences, or facts for later retrieval. "
        "Use 'recall' to search for stored information when the user asks about past context or personal details. "
        "Always confirm when information has been successfully stored."
    )

    worker = WorkerAgent(
        model=model,
        tools=memory_tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node()
