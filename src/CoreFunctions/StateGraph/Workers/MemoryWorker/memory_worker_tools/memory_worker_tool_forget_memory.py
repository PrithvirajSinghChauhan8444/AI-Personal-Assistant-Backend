import json
import os
from langchain_core.tools import StructuredTool

# Import all infra helpers that tools might need
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector, delete_vector_fact, rebuild_skills_vector_store, search_skills_vector
from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory


def forget_memory(key: str, category: str = "user") -> str:
    """Deletes a structured key-value memory from the database.

    Args:
        key (str): The unique identifier of the memory to delete.
        category (str): The category the memory belongs to (e.g., 'user', 'past'). Defaults to 'user'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: forget_memory")
    print(f"   Args: key={key}, category={category}")
    try:
        msg = delete_memory(category, key)
        return msg
    except Exception as e:
        return f"Error deleting memory: {e}"

memory_worker_tool_forget_memory = StructuredTool.from_function(
    func=forget_memory,
    name="forget_memory",
    description="Permanently deletes a specific memory key and its structured data from the database."
)
