from src.CoreFunctions.SharedTools import human_intervention_tool, get_time_tool, get_weather_tool, web_search_tool
from src.CoreFunctions.StateGraph.Workers.MemoryWorker.memory_worker_tools import memory_worker_tool_list_active_workers
from .productivity_worker_tool_add_task import productivity_worker_tool_add_task
from .productivity_worker_tool_check_events import productivity_worker_tool_check_events
from .productivity_worker_tool_add_event import productivity_worker_tool_add_event

# System health is in tools.py, let's export it as a tool
from src.CoreFunctions.StateGraph.Workers.SystemWorker.system_worker_tools.system_worker_tool_get_system_health import system_worker_tool_get_system_health

calendar_tools = [
    productivity_worker_tool_add_task,
    productivity_worker_tool_check_events,
    productivity_worker_tool_add_event,
    system_worker_tool_get_system_health,
    get_weather_tool,
    get_time_tool,
    web_search_tool,
    memory_worker_tool_list_active_workers,
    human_intervention_tool
]
