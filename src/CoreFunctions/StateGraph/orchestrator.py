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
                
    if not executable_tasks:
        # Check if there are still pending/in_progress tasks
        has_unfinished = any(t["status"] in ["pending", "in_progress"] for t in active_subtasks)
        if has_unfinished:
            print("  -> Execution waiting on active subtask dependencies.")
            # Yield to Orchestrator self-loop or a pause
            return {
                "next_node": "Orchestrator"
            }
        else:
            print("  -> All tasks completed. Routing to Output Finalizer.")
            return {
                "next_node": "OutputFinalizer"
            }

    # If multiple tasks can be executed concurrently, run them in parallel!
    if len(executable_tasks) > 1:
        print(f"\n⚡ [Parallel Executor] Concurrently executing {len(executable_tasks)} independent tasks:")
        for t in executable_tasks:
            print(f"  - [{t['assigned_worker']}] {t['description']}")
            # Mark as in_progress immediately
            for st in active_subtasks:
                if st["id"] == t["id"]:
                    st["status"] = "in_progress"

        from src.CoreFunctions.StateGraph.workers import _run_ephemeral_agent

        def run_task(task):
            try:
                result = _run_ephemeral_agent(task["assigned_worker"], task["description"], state.get("working_memory", {}) or {})
                return task["id"], result, None
            except Exception as ex:
                return task["id"], None, str(ex)

        results = []
        with ThreadPoolExecutor(max_workers=len(executable_tasks)) as executor:
            futures = [executor.submit(run_task, t) for t in executable_tasks]
            for fut in futures:
                results.append(fut.result())

        # Update state sequentially after parallel threads join
        working_memory = state.get("working_memory", {}) or {}
        completed_tasks = state.get("completed_tasks", {}) or {}
        error_logs = state.get("error_logs", "") or ""

        for task_id, res_data, err in results:
            for st in active_subtasks:
                if st["id"] == task_id:
                    if err:
                        st["status"] = "failed"
                        error_logs += f"\nTask {task_id} failed: {err}"
                        print(f"  ❌ [{st['assigned_worker']}] Task {task_id} failed concurrently: {err}")
                    else:
                        st["status"] = "completed"
                        working_memory[task_id] = res_data
                        completed_tasks[task_id] = res_data
                        print(f"  ✔ [\033[1;32m{st['assigned_worker']} Parallel Finish\033[0m]: Completed task {task_id} successfully.")

        # Return to Orchestrator to evaluate next task steps
        return {
            "active_subtasks": active_subtasks,
            "working_memory": working_memory,
            "completed_tasks": completed_tasks,
            "error_logs": error_logs if error_logs else None,
            "next_node": "Orchestrator"
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
    """Conditional edge function to map next_node to the actual node"""
    next_node = state.get("next_node", "OutputFinalizer")
    # Loop back to Orchestrator if specified
    if next_node == "Orchestrator":
        return "Orchestrator"
    return next_node
