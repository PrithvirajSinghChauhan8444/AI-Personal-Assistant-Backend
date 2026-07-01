import json
import os
from langchain_core.tools import StructuredTool

# Import all infra helpers that tools might need
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector, delete_vector_fact, rebuild_skills_vector_store, search_skills_vector
from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory


def delete_fact(fact_text: str) -> str:
    """Removes a specific fact from the vector database.

    Args:
        fact_text (str): The exact text of the fact to remove.
        
    Note: Fact text must match exactly (case-insensitive).
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: delete_fact")
    print(f"   Args: fact_text={fact_text}")
    try:
        success = delete_vector_fact(fact_text)
        if success:
            return f"Successfully removed fact: \"{fact_text}\""
        return f"Fact not found in vector store: \"{fact_text}\""
    except Exception as e:
        return f"Error removing fact: {e}"

memory_worker_tool_delete_fact = StructuredTool.from_function(
    func=delete_fact,
    name="delete_fact",
    description="Deletes a specific unstructured fact from the vector database by matching its text."
)
