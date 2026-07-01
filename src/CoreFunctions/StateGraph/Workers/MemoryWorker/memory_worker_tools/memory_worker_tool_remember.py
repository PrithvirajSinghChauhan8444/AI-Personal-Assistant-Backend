import json
import os
from langchain_core.tools import StructuredTool

# Import all infra helpers that tools might need
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector, delete_vector_fact, rebuild_skills_vector_store, search_skills_vector
from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory


def remember(key: str, value: str, category: str = "past") -> str:
    """Store important information for future use.

    Args:
        key (str): The unique identifier or topic name for the memory (e.g., 'user_name').
        value (str): The actual details or context to remember (e.g., 'John' or a structured dictionary/list).
        category (str): The grouping category for the memory. Defaults to 'past'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: remember")
    print(f"   Args: key={key}, value={value}, category={category}")
    store_memory(category, key, value)
    value_str = value if isinstance(value, str) else json.dumps(value)
    store_vector(value_str)
    return f"Saved memory: {key}"

memory_worker_tool_remember = StructuredTool.from_function(
    func=remember,
    name="remember",
    description="Store or save a fact, key information, or context to permanent memory."
)
