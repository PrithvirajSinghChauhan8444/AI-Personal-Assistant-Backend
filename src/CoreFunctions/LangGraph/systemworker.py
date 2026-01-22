from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import system_control_tools, file_management_tools, system_info_tools

def create_system_worker(model):
    """
    Creates the SystemWorker node.
    """
    system_prompt = (
        "You are the SystemWorker, an autonomous intelligent agent with distinct capabilities. "
        "Your core role is to interface with the operating system to perform file operations, "
        "execute terminal commands, run python scripts, and manage applications. "
        "You have access to a suite of system tools to achieve these tasks. "
        "Analyze the user's request, determine the most effective sequence of tool usage, "
        "and execute it. You do not need explicit instructions on which tool to use; "
        "use your judgment to select the best tool for the job. "
        "Always report the outcome of your actions clearly."
    )

    # Combine tools relevant for system operations
    tools = system_control_tools + file_management_tools + system_info_tools

    worker = WorkerAgent(
        model=model,
        tools=tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node(name="SystemWorker")
