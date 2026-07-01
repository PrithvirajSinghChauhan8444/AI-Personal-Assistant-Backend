import json
import os
from langchain_core.tools import StructuredTool

# Import all infra helpers that tools might need
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector, delete_vector_fact, rebuild_skills_vector_store, search_skills_vector
from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory


def recall(key: str) -> str:
    """Recall memory by key using smart lookup. Checks the structured SQL/Redis database first, then falls back to vector database search.

    Args:
        key (str): The unique identifier or topic name of the memory to fetch.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: recall")
    print(f"   Args: key={key}")
    # 1. Search structured memory first (SQL / Redis)
    value = fetch_memory(None, key)
    if value is not None:
        return value
        
    # 2. Fallback to vector search if no structured key matches
    from src.CoreFunctions.Infrastructure.vector_memory import search_vector
    vector_results = search_vector(key, k=3, threshold=1.15)
    if vector_results:
        return "\n".join(vector_results)
        
    return f"No memory found for '{key}'."

memory_worker_tool_recall = StructuredTool.from_function(
    func=recall,
    name="recall",
    description="Retrieve stored facts, information, or context from permanent memory matching a search term."
)
