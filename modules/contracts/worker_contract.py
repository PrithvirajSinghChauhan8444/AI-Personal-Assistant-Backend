from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from modules.contracts.state_contract import AgentState

class BaseWorkerProtocol(ABC):
    """Protocol for independent domain workers.
    Each worker module implements this protocol without depending on other workers.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the worker (e.g. 'SystemWorker', 'GmailWorker')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief mandate of the worker for intent routing."""
        pass

    @property
    @abstractmethod
    def instructions(self) -> str:
        """System prompt instructions for this worker."""
        pass

    @property
    @abstractmethod
    def tools(self) -> list:
        """Tools private to this worker."""
        pass

    @property
    def categories(self) -> List[str]:
        return [self.name]

    @property
    def routing_rules(self) -> List[str]:
        return []

    @property
    def is_graph_node(self) -> bool:
        return True

    @abstractmethod
    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a single task in isolation and returns output payload.
        Contract: takes task_id, description, context -> returns {'status': ..., 'summary': ..., 'data': ...}
        """
        pass

    def execute(self, state: AgentState) -> Dict[str, Any]:
        """LangGraph node execution wrapper conforming to state graph."""
        active_subtasks = state.get("active_subtasks", [])
        working_memory = state.get("working_memory", {}) or {}
        
        # Find current assigned task
        current_task = None
        for st in active_subtasks:
            if st.get("assigned_worker") == self.name and st.get("status") == "in_progress":
                current_task = st
                break
                
        if not current_task:
            return {}

        task_id = current_task.get("id", "task_unknown")
        desc = current_task.get("description", "")
        
        # Sandboxed context: only pass inputs relevant to this task
        context = {
            "working_memory": {k: v for k, v in working_memory.items() if not k.startswith("_")},
            "task": current_task
        }
        
        result = self.execute_task(task_id, desc, context)
        
        status = result.get("status", "completed")
        summary = result.get("summary", "")
        data_payload = result.get("data", {})
        
        return {
            "active_subtasks": [{
                "id": task_id,
                "status": status,
                "result": summary
            }],
            "completed_tasks": {
                task_id: {
                    "worker": self.name,
                    "description": desc,
                    "summary": summary,
                    "status": status
                }
            },
            "working_memory": data_payload
        }
