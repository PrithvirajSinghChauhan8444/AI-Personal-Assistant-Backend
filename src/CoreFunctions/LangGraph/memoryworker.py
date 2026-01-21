from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import memory_tools

def create_memory_worker(model):
    """
    Creates the MemoryWorker node.
    """
    system_prompt = (
        "You are the MemoryWorker, the keeper of long-term knowledge for the assistant. "
        "Your capabilities include storing important user details, preferences, and facts, "
        "as well as retrieving this context when needed. "
        "You are equipped with tools to persist and recall information. "
        "Proactively decide when a piece of information is worth remembering for the future, "
        "and when to query your knowledge base to provide better context for the current conversation. "
        "Ensure data is stored accurately and confirm successful operations."
    )

    worker = WorkerAgent(
        model=model,
        tools=memory_tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node()
