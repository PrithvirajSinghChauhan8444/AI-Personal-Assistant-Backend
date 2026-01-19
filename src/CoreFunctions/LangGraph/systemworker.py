from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import system_control_tools, file_management_tools, system_info_tools

def create_system_worker(model):
    """
    Creates the SystemWorker node.
    """
    system_prompt = (
        "You are the SystemWorker. "
        "Your capabilities include running terminal commands, python scripts, file operations, "
        "and launching applications. "
        "You should use the available tools to fulfill the user's request efficiently. "
        "If you have completed the action, simply state what you did."
    )

    # Combine tools relevant for system operations
    tools = system_control_tools + file_management_tools + system_info_tools

    worker = WorkerAgent(
        model=model,
        tools=tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node()
