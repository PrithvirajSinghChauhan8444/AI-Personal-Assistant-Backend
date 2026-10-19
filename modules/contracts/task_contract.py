from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class SubTaskModel(BaseModel):
    id: str = Field(description="Unique identifier for the subtask, e.g., 'task_1'")
    description: str = Field(description="Clear execution instructions for the worker")
    assigned_worker: str = Field(description="Target worker module name")
    depends_on: List[str] = Field(default_factory=list, description="IDs of tasks that must finish before this executes")
    confidence_score: float = Field(default=1.0, description="Confidence score from 0.0 to 1.0")
    confidence_reason: str = Field(default="Direct assignment", description="Reasoning behind this task plan step")
    entity_reference: Optional[str] = Field(default=None, description="Referenced entity key or context variable")

class TaskPlan(BaseModel):
    primary_goal: str = Field(description="User prompt being addressed")
    subtasks: List[SubTaskModel] = Field(description="List of subtasks and their operational dependency graph")

class WorkerCapability(BaseModel):
    name: str
    description: str
    routing_rules: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)

class WorkerExecutionResult(BaseModel):
    worker_name: str
    task_id: str
    status: str  # "completed", "failed"
    summary: str
    data_payload: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
