from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import memory_tools

def create_memory_worker(model):
    """
    Creates the MemoryWorker node.
    """
    system_prompt = (
        "You are the MemoryWorker. Your role is to store and recall user facts and context.\n"
        "Proactively remember important details and retrieve them when relevant.\n"
        "Always report results clearly and concisely.\n\n"
        "### EXAMPLES\n"
        "User: 'My favorite color is Blue'\n"
        "Action: calls `store_fact(fact='User favorite color: Blue')` -> 'I'll remember that your favorite color is Blue.'\n\n"
        "User: 'What is my favorite color?'\n"
        "Action: calls `query_memory(query='favorite color')` -> 'Your favorite color is Blue.'\n\n"
        "User: 'Where do I live?'\n"
        "Action: calls `query_memory(query='user location')` -> 'I don't have that information in my memory yet.'"
    )

    worker = WorkerAgent(
        model=model,
        tools=memory_tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node(name="MemoryWorker")
