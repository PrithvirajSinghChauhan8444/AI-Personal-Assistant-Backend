from typing import List, Dict, Any, Tuple, Optional, Union
from modules.contracts.state_contract import AgentState, SubTask
from modules.infrastructure.observability.telemetry import get_module_tracer

tracer = get_module_tracer("orchestrator")

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
        with tracer.start_as_current_span("orchestrator.evaluate_queue") as span:
            span.set_attribute("orchestrator.active_subtasks_count", len(active_subtasks))
            span.set_attribute("orchestrator.completed_tasks_count", len(completed_tasks))

            if not active_subtasks:
                span.set_attribute("orchestrator.decision", "route_to_finalizer_empty")
                return ["OutputFinalizer"], []


        WORKER_ALIASES = {
            "CalendarWorker": "ProductivityWorker",
            "TasksWorker": "ProductivityWorker",
            "EmailWorker": "CommunicationWorker",
            "GmailWorker": "CommunicationWorker",
            "MailWorker": "CommunicationWorker",
            "FileWorker": "SystemWorker",
            "TerminalWorker": "SystemWorker",
            "DriveWorker": "GoogleDriveWorker",
            "GoogleDriveManager": "GoogleDriveWorker",
            "BrowserNavigator": "BrowserWorker",
            "BrowserReader": "BrowserWorker",
            "ObsidianNoteWorker": "ObsidianWorker",
            "ObsidianCanvasWorker": "ObsidianWorker",
            "ObsidianRefactorWorker": "ObsidianWorker",
            "YouTubeWorker": "YoutubeWorker"
        }

        # Normalize worker names in active subtasks
        for st in active_subtasks:
            worker = st.get("assigned_worker")
            if worker in WORKER_ALIASES:
                st["assigned_worker"] = WORKER_ALIASES[worker]

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

        # Check in_progress tasks
        in_progress_tasks = [st for st in active_subtasks if st.get("status") == "in_progress"]

        # Handle deadlock: pending tasks exist, but none are ready and none are in_progress
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
            # If tasks are already in_progress, route to their worker to complete them
            if in_progress_tasks:
                target_worker = in_progress_tasks[0].get("assigned_worker")
                if target_worker:
                    return [target_worker], []
            return ["OutputFinalizer"], []

        # Select ready tasks to dispatch, ensuring at most ONE task per unique worker
        dispatched_tasks = []
        workers_seen = set()
        for st in ready_tasks:
            worker_name = st.get("assigned_worker")
            if worker_name and worker_name not in workers_seen:
                workers_seen.add(worker_name)
                dispatched_tasks.append(st)
                if not self.allow_parallel or len(dispatched_tasks) >= self.max_parallel:
                    break

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
