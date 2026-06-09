from typing import TypedDict, List, Dict, Any, Optional, Annotated

class SubTask(TypedDict):
    id: str
    description: str
    assigned_worker: str # "SystemWorker", "GmailWorker", "ProductivityWorker", "MemoryWorker"
    status: str # "pending", "in_progress", "completed", "failed"
    depends_on: List[str]

def merge_subtasks(left: List[SubTask], right: List[SubTask]) -> List[SubTask]:
    """Reducer to merge active subtasks by ID, preserving modifications from concurrent executions."""
    if left is None:
        left = []
    if right is None:
        right = []
    merged = {st["id"]: st for st in left}
    for st in right:
        if st["id"] in merged:
            merged[st["id"]] = {**merged[st["id"]], **st}
        else:
            merged[st["id"]] = st
    return list(merged.values())

def merge_dict(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer to merge dictionaries (e.g. working_memory and completed_tasks)."""
    if left is None:
        left = {}
    if right is None:
        right = {}
    return {**left, **right}

class AgentState(TypedDict):
    primary_goal: str
    active_subtasks: Annotated[List[SubTask], merge_subtasks]
    working_memory: Annotated[Dict[str, Any], merge_dict]
    completed_tasks: Annotated[Dict[str, Any], merge_dict]
    error_logs: Optional[str]
    final_response: str
    next_node: Any  # Can be str or List[str] for parallel routing
    chat_history: Optional[List[Dict[str, str]]]

