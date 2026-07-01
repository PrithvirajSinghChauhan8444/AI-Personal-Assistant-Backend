from src.CoreFunctions.SharedTools import human_intervention_tool
from .memory_worker_tool_recall import memory_worker_tool_recall
from .memory_worker_tool_remember import memory_worker_tool_remember
from .memory_worker_tool_update_unified_memory import memory_worker_tool_update_unified_memory
from .memory_worker_tool_forget_memory import memory_worker_tool_forget_memory
from .memory_worker_tool_delete_fact import memory_worker_tool_delete_fact
from .memory_worker_tool_list_keys import memory_worker_tool_list_keys
from .memory_worker_tool_update_skill import memory_worker_tool_update_skill
from .memory_worker_tool_list_active_workers import memory_worker_tool_list_active_workers
from .memory_worker_tool_search_skills import memory_worker_tool_search_skills

memory_tools = [
    memory_worker_tool_recall,
    memory_worker_tool_remember,
    memory_worker_tool_update_unified_memory,
    memory_worker_tool_forget_memory,
    memory_worker_tool_delete_fact,
    memory_worker_tool_list_keys,
    memory_worker_tool_update_skill,
    memory_worker_tool_list_active_workers,
    memory_worker_tool_search_skills,
    human_intervention_tool
]
