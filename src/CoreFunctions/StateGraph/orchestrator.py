from src.CoreFunctions.StateGraph.state import AgentState
from concurrent.futures import ThreadPoolExecutor

def orchestrator_node(state: AgentState):
    print("\n[Node: Orchestrator] Evaluating task execution graph...")
    active_subtasks = state.get("active_subtasks", []) or []
    completed_task_ids = {t["id"] for t in active_subtasks if t["status"] == "completed"}
    
    # Gather all executable tasks whose dependencies are fully completed
    executable_tasks = []
    for task in active_subtasks:
        if task["status"] == "pending":
            depends_on = task.get("depends_on", [])
            deps_satisfied = all(dep in completed_task_ids for dep in depends_on)
            if deps_satisfied:
                executable_tasks.append(task)

    # Filter executable_tasks to ensure we only run one task per worker at a time,
    # and do not run a task for a worker that is already executing an in_progress task.
    if executable_tasks:
        running_workers = {t["assigned_worker"] for t in active_subtasks if t["status"] == "in_progress"}
        unique_worker_tasks = []
        for task in executable_tasks:
            worker = task["assigned_worker"]
            if worker not in running_workers:
                running_workers.add(worker)
                unique_worker_tasks.append(task)
        executable_tasks = unique_worker_tasks
                
    if not executable_tasks:
        # Check if there are still pending/in_progress tasks
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

    # If multiple tasks can be executed concurrently, route to them in parallel using LangGraph branching!
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

def orchestrator_router(state: AgentState):
    """Conditional edge function mapping next_node state to one or more execution nodes."""
    next_node = state.get("next_node")
    if not next_node:
        return "OutputFinalizer"
    # Can return a single string or a list of strings for parallel execution
    return next_node
