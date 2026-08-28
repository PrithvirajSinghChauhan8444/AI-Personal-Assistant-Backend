from typing import List, Dict, Any, Set
from src.CoreFunctions.StateGraph.state import AgentState

def _get_pending_tasks_with_satisfied_deps(active_subtasks: List[Dict[str, Any]], completed_task_ids: Set[str]) -> List[Dict[str, Any]]:
    """Gathers all pending tasks whose dependencies are fully completed."""
    executable_tasks = []
    for task in active_subtasks:
        if task["status"] == "pending":
            depends_on = task.get("depends_on", [])
            deps_satisfied = all(dep in completed_task_ids for dep in depends_on)
            if deps_satisfied:
                executable_tasks.append(task)
    return executable_tasks

def _filter_by_worker_availability(executable_tasks: List[Dict[str, Any]], active_subtasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filters executable_tasks to ensure we only run one task per worker at a time,
    and do not run a task for a worker that is already executing an in_progress task."""
    running_workers = {t["assigned_worker"] for t in active_subtasks if t["status"] == "in_progress"}
    unique_worker_tasks = []
    for task in executable_tasks:
        worker = task["assigned_worker"]
        if worker not in running_workers:
            running_workers.add(worker)
            unique_worker_tasks.append(task)
    return unique_worker_tasks

def _handle_no_executable_tasks(active_subtasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Handles routing and state updates when no tasks are currently executable."""
    has_in_progress = any(t["status"] == "in_progress" for t in active_subtasks)
    has_pending = any(t["status"] == "pending" for t in active_subtasks)
    
    if has_in_progress:
        print("  ⚠️ Found orphaned 'in_progress' tasks (likely from a previous interrupted run). Resetting to 'pending'...")
        for t in active_subtasks:
            if t["status"] == "in_progress":
                t["status"] = "pending"
        return {
            "active_subtasks": active_subtasks,
            "next_node": "Orchestrator"
        }
    elif has_pending:
        # Deadlock: pending tasks exist but nothing is running to satisfy them (e.g. dependency failed)
        print("  ⚠️ Dependency deadlock detected! Aborting blocked pending tasks.")
        for t in active_subtasks:
            if t["status"] == "pending":
                t["status"] = "failed"
        return {
            "active_subtasks": active_subtasks,
            "next_node": "OutputFinalizer"
        }
    else:
        print("  -> All tasks completed. Routing to Output Finalizer.")
        return {
            "next_node": "OutputFinalizer"
        }

def _dispatch_executable_tasks(executable_tasks: List[Dict[str, Any]], active_subtasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Updates subtask statuses and sets the next_node to route the execution."""
    if len(executable_tasks) > 1:
        print(f"\n⚡ [Parallel DAG Branching] Concurrently routing to {len(executable_tasks)} independent workers:")
        next_nodes = []
        for t in executable_tasks:
            worker = t["assigned_worker"]
            print(f"  - [{worker}] {t['description']}")
            next_nodes.append(worker)
            # Mark as in_progress immediately so the worker can pick it up
            for st in active_subtasks:
                if st["id"] == t["id"]:
                    st["status"] = "in_progress"

        return {
            "active_subtasks": active_subtasks,
            "next_node": next_nodes
        }
        
    else:
        # Standard sequential path: single executable task
        next_task = executable_tasks[0]
        worker_name = next_task["assigned_worker"]
        
        # Mark as in_progress immediately
        for st in active_subtasks:
            if st["id"] == next_task["id"]:
                st["status"] = "in_progress"
                break
                
        print(f"  -> Single task executable. Delegating to {worker_name} for task: {next_task['id']}")
        return {
            "active_subtasks": active_subtasks,
            "next_node": worker_name
        }

def orchestrator_node(state: AgentState) -> Dict[str, Any]:
    """Evaluates task execution graph, identifies executable tasks, and routes execution."""
    print("\n[Node: Orchestrator] Evaluating task execution graph...")
    active_subtasks = state.get("active_subtasks", []) or []
    completed_task_ids = {t["id"] for t in active_subtasks if t["status"] == "completed"}
    
    # 1. Gather all tasks whose dependencies are met
    executable_tasks = _get_pending_tasks_with_satisfied_deps(active_subtasks, completed_task_ids)

    # NEW CONFIDENCE INTERCEPTION GUARDRAIL:
    CONFIDENCE_THRESHOLD = 0.80
    for task in executable_tasks:
        score = task.get("confidence_score", 1.0)
        if score < CONFIDENCE_THRESHOLD:
            reason = task.get("confidence_reason", "Low confidence target context.")
            ref = task.get("entity_reference", "")
            print(f"\n  🛑 [Confidence Guardrail] Intercepted low-confidence task {task['id']} (Score: {score:.2f})!")
            print(f"     Reason: {reason} | Reference: {ref}")
            
            # Abort all remaining non-completed tasks
            for t in active_subtasks:
                if t["status"] in ["pending", "in_progress"]:
                    t["status"] = "failed"
            
            clarification_msg = (
                f"I stopped executing your request because I am not sure about the context: {reason}.\n"
                f"Could you please clarify who or what you are referring to?"
            )
            return {
                "active_subtasks": active_subtasks,
                "final_response": clarification_msg,
                "next_node": "OutputFinalizer"
            }

    # 2. Filter tasks to avoid duplicate/overlapping worker executions
    if executable_tasks:
        executable_tasks = _filter_by_worker_availability(executable_tasks, active_subtasks)
                
    # 3. Handle when no tasks are currently runnable (deadlocks, orphan recovery, completion)
    if not executable_tasks:
        return _handle_no_executable_tasks(active_subtasks)

    # 4. Dispatch the runnable tasks (sequential or parallel routing)
    return _dispatch_executable_tasks(executable_tasks, active_subtasks)

def orchestrator_router(state: AgentState):
    """Conditional edge function mapping next_node state to one or more execution nodes."""
    next_node = state.get("next_node")
    if not next_node:
        return "OutputFinalizer"
    # Can return a single string or a list of strings for parallel execution
    return next_node
