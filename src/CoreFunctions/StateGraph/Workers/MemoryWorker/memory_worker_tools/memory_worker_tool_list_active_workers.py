import json
import os
from langchain_core.tools import StructuredTool

# Import all infra helpers that tools might need
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector, delete_vector_fact, rebuild_skills_vector_store, search_skills_vector
from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory


def list_active_workers_tool() -> str:
    """Returns a list of all currently registered and configured workers, including their status (active/inactive) and model.
    Use this to see which agents/workers are currently loaded in the assistant.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: list_active_workers_tool")
    try:
        from src.CoreFunctions.StateGraph.registry import WorkerRegistry
        if not hasattr(WorkerRegistry, "_config") or not WorkerRegistry._config:
            WorkerRegistry.load_and_sync_config()
            
        all_workers = WorkerRegistry._registry
        config = WorkerRegistry._config
        
        lines = []
        for name, worker in all_workers.items():
            status = "Active" if config.get(name, {}).get("active", True) else "Inactive"
            model = config.get(name, {}).get("model", "default")
            lines.append(f"- {name}: {worker.description} | Status: {status} | Model: {model}")
            
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing workers: {e}"

memory_worker_tool_list_active_workers = StructuredTool.from_function(
    func=list_active_workers_tool,
    name="list_active_workers",
    description="Returns list of registered active worker names and details on what they do."
)
