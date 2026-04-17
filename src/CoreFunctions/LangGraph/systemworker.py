from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import system_control_tools, file_management_tools, system_info_tools

def create_system_worker(model):
    """
    Creates the SystemWorker node.
    """
    system_prompt = (
        "You are the SystemWorker. Your role is to interface with the OS (files, commands, stats).\n"
        "Analyze the request, select the best tool, and execute. Use your judgment.\n"
        "Always report results clearly and concisely.\n\n"
        "### EXAMPLES\n"
        "User: 'Check CPU and RAM'\n"
        "Action: calls `get_system_stats` -> 'CPU: 10%, RAM: 4.2GB/16GB'\n\n"
        "User: 'List files in home'\n"
        "Action: calls `list_files(path='~')` -> 'Found 5 files: a.txt, b.py...'\n\n"
        "User: 'Run the backup script'\n"
        "Action: calls `execute_command(command='bash backup.sh')` -> 'Script executed successfully. Output: Done.'"
    )

    # Combine tools relevant for system operations
    tools = system_control_tools + file_management_tools + system_info_tools

    worker = WorkerAgent(
        model=model,
        tools=tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node(name="SystemWorker")
