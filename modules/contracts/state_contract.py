from typing import TypedDict, List, Dict, Any, Optional, Annotated

class SubTask(TypedDict, total=False):
    id: str
    description: str
    assigned_worker: str
    status: str  # "pending", "in_progress", "completed", "failed", "aborted"
    depends_on: List[str]
    confidence_score: float
    confidence_reason: str
    entity_reference: Optional[str]
    payload: Dict[str, Any]
    result: Optional[str]
    error: Optional[str]

def merge_subtasks(left: Optional[List[SubTask]], right: Optional[List[SubTask]]) -> List[SubTask]:
    """Reducer to merge active subtasks by ID, preserving modifications from concurrent executions."""
    if left is None:
        left = []
    if right is None:
        right = []
    merged = {st["id"]: dict(st) for st in left if "id" in st}
    for st in right:
        st_id = st.get("id")
        if not st_id:
            continue
        if st_id in merged:
            merged[st_id].update(st)
        else:
            merged[st_id] = dict(st)
    return list(merged.values())

def merge_dict(left: Optional[Dict[str, Any]], right: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Reducer to merge dictionaries (e.g. working_memory and completed_tasks)."""
    if left is None:
        left = {}
    if right is None:
        right = {}
    merged = dict(left)
    merged.update(right)
    return merged

def merge_error_logs(left: Optional[List[str]], right: Optional[List[str]]) -> List[str]:
    """Reducer to merge error lists preserving all recorded failures."""
    if left is None:
        left = []
    if right is None:
        right = []
    if isinstance(left, str):
        left = [left]
    if isinstance(right, str):
        right = [right]
    merged = list(left)
    for err in right:
        if err not in merged:
            merged.append(err)
    return merged

class AgentState(TypedDict, total=False):
    primary_goal: str
    active_subtasks: Annotated[List[SubTask], merge_subtasks]
    working_memory: Annotated[Dict[str, Any], merge_dict]
    completed_tasks: Annotated[Dict[str, Any], merge_dict]
    error_logs: Annotated[List[str], merge_error_logs]
    final_response: str
    next_node: Any
    chat_history: Optional[List[Dict[str, str]]]
    system_state: Optional[Dict[str, Any]]
