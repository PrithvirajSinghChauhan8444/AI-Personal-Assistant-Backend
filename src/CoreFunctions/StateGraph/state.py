from typing import TypedDict, List, Dict, Any, Optional

class SubTask(TypedDict):
    id: str
    description: str
    assigned_worker: str # "SystemWorker", "GmailWorker", "ProductivityWorker", "MemoryWorker"
    status: str # "pending", "in_progress", "completed", "failed"
    depends_on: List[str]

class AgentState(TypedDict):
    primary_goal: str
    active_subtasks: List[SubTask]
    working_memory: Dict[str, Any]
    completed_tasks: Dict[str, Any]
    error_logs: Optional[str]
    final_response: str
    next_node: str
    chat_history: Optional[List[Dict[str, str]]]

