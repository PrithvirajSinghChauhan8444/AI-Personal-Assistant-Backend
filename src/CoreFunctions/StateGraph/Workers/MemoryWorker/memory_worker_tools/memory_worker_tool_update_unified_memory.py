import json
import os
from langchain_core.tools import StructuredTool

# Import all infra helpers that tools might need
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector, delete_vector_fact, rebuild_skills_vector_store, search_skills_vector
from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory


def update_unified_memory(key: str, value: str, category: str = "user") -> str:
    """Updates or saves a key-value pair directly in the Unified Memory database,
    and updates the semantic vector database with the fact.
    
    Args:
        key (str): The unique identifier of the memory key (e.g. 'GmailWorker').
        value (str): The string value/content to store.
        category (str): The category under which to store (user/past/current). Defaults to 'user'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: update_unified_memory")
    print(f"   Args: key={key}, value={value}, category={category}")
    try:
        # Save to structured memory
        store_memory(category, key, value)
        
        # Save to vector memory
        from src.CoreFunctions.Infrastructure.vector_memory import store_vector
        vector_fact = f"The value of {key} in unified memory is: {value}."
        store_vector(vector_fact)
        
        return f"Successfully updated memory key '{key}' to '{value}'."
    except Exception as e:
        return f"Error updating unified memory: {e}"

memory_worker_tool_update_unified_memory = StructuredTool.from_function(
    func=update_unified_memory,
    name="update_unified_memory",
    description="Updates or modifies an existing memory key with a new value in the database."
)
