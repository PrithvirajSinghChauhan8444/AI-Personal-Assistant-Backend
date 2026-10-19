from typing import List, Dict, Any, Tuple, Optional, Union
from modules.contracts.state_contract import AgentState, SubTask

class TaskScheduler:
    """Independent Execution Orchestrator & State Machine Scheduler.
    Determines next executable worker tasks based strictly on task dependencies and completion statuses.
    """
    def __init__(self, allow_parallel: bool = True, max_parallel: int = 4, auto_heal_deadlocks: bool = True):
        self.allow_parallel = allow_parallel
        self.max_parallel = max_parallel
        self.auto_heal_deadlocks = auto_heal_deadlocks

    def evaluate_queue(self, active_subtasks: List[SubTask], completed_tasks: Dict[str, Any]) -> Tuple[List[str], List[SubTask]]:
        """Evaluates subtasks and returns:
        1. target_workers: list of worker names to invoke next
        2. updated_subtasks: task list with newly in_progress statuses
        """
        if not active_subtasks:
            return ["OutputFinalizer"], []

        # Map completed task IDs
        completed_ids = set(completed_tasks.keys())
        for st in active_subtasks:
            if st.get("status") == "completed":
                completed_ids.add(st["id"])

        # Check if all tasks are complete or aborted
        all_done = all(st.get("status") in ["completed", "aborted", "failed"] for st in active_subtasks)
        if all_done:
            return ["OutputFinalizer"], []

        # Find ready pending tasks whose dependencies are satisfied
        ready_tasks = []
        for st in active_subtasks:
            if st.get("status") == "pending":
                deps = st.get("depends_on", [])
                if all(dep in completed_ids for dep in deps):
                    ready_tasks.append(st)

        # Handle deadlock: pending tasks exist, but none are ready and none are in_progress
        in_progress_tasks = [st for st in active_subtasks if st.get("status") == "in_progress"]
        if not ready_tasks and not in_progress_tasks:
            if self.auto_heal_deadlocks:
                # Mark remaining blocked tasks as aborted
                updated_subtasks = []
                for st in active_subtasks:
                    if st.get("status") == "pending":
                        st_copy = dict(st)
                        st_copy["status"] = "aborted"
                        st_copy["error"] = "Dependency blocked / deadlocked"
                        updated_subtasks.append(st_copy)
                return ["OutputFinalizer"], updated_subtasks
            return ["OutputFinalizer"], []

        if not ready_tasks:
            # Some tasks are still in progress; wait or cycle
            return ["Orchestrator"], []

        # Select tasks to dispatch
        dispatched_tasks = ready_tasks[:self.max_parallel] if self.allow_parallel else ready_tasks[:1]
        target_workers = [st["assigned_worker"] for st in dispatched_tasks]

        # Update dispatched tasks to in_progress
        updated_subtasks = []
        for st in dispatched_tasks:
            st_copy = dict(st)
            st_copy["status"] = "in_progress"
            updated_subtasks.append(st_copy)

        return target_workers, updated_subtasks

    def as_node(self, state: AgentState) -> Dict[str, Any]:
        """LangGraph node compatible function."""
        active_subtasks = state.get("active_subtasks", []) or []
        completed_tasks = state.get("completed_tasks", {}) or {}

        targets, updated_subtasks = self.evaluate_queue(active_subtasks, completed_tasks)

        res: Dict[str, Any] = {}
        if updated_subtasks:
            res["active_subtasks"] = updated_subtasks

        # next_node can be single string or list of workers for parallel execution
        if len(targets) == 1:
            res["next_node"] = targets[0]
        else:
            res["next_node"] = targets

        return res

    @staticmethod
    def router_fn(state: AgentState) -> Union[str, List[str]]:
        """Conditional routing function for LangGraph."""
        next_node = state.get("next_node")
        if not next_node:
            return "OutputFinalizer"
        return next_node
