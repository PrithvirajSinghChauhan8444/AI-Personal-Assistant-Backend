import json
import os
from langchain_core.tools import StructuredTool

# Import all infra helpers that tools might need
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector, delete_vector_fact, rebuild_skills_vector_store, search_skills_vector
from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory


def list_memory_keys(pattern: str = "*") -> str:
    """Lists all available memory keys stored in the unified memory database matching the glob pattern.

    Args:
        pattern (str): The glob pattern to filter keys (e.g. '*'). Defaults to '*'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: list_memory_keys")
    print(f"   Args: pattern={pattern}")
    from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory
    um = UnifiedMemory()
    if not um.enabled:
        return "Unified Memory is disabled."
    keys = um.list_keys(pattern)
    if not keys:
        return f"No memory keys matching '{pattern}' found."
    return "Available memory keys:\n" + "\n".join([f"- {k}" for k in keys])

memory_worker_tool_list_keys = StructuredTool.from_function(
    func=list_memory_keys,
    name="list_memory_keys",
    description="Lists all available memory keys stored in the unified memory database matching the glob pattern."
)
