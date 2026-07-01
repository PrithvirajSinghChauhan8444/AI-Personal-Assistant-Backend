from src.CoreFunctions.SharedTools import human_intervention_tool, run_terminal_tool_wrapped, run_python_tool_wrapped, web_search_tool
from src.CoreFunctions.StateGraph.Workers.SystemWorker.system_worker_tools.system_worker_tool_read_file import read_file_tool
from src.CoreFunctions.StateGraph.Workers.SystemWorker.system_worker_tools.system_worker_tool_create_file import create_file_tool
from src.CoreFunctions.StateGraph.Workers.MemoryWorker.memory_worker_tools import memory_worker_tool_update_skill, memory_worker_tool_search_skills

# Custom automation tools can be imported here if any. E.g. ytmusic tools.
misc_tools = [
    run_terminal_tool_wrapped,
    run_python_tool_wrapped,
    web_search_tool,
    read_file_tool,
    create_file_tool,
    memory_worker_tool_update_skill,
    memory_worker_tool_search_skills,
    human_intervention_tool
]
