from src.CoreFunctions.StateGraph.state import AgentState

def orchestrator_node(state: AgentState):
    print("\n[Node: Orchestrator] Evaluating state...")
    active_subtasks = state.get("active_subtasks", [])
    
    # Find the first pending task
    next_task = None
    for i, task in enumerate(active_subtasks):
        if task["status"] == "pending":
            next_task = task
            # Mark it as in progress immediately
            active_subtasks[i]["status"] = "in_progress"
            break
            
    if next_task:
        worker_name = next_task["assigned_worker"]
        print(f"  -> Delegating to {worker_name} for task: {next_task['id']}")
        return {
            "active_subtasks": active_subtasks,
            "next_node": worker_name
        }
    else:
        # All tasks completed
        print("  -> All tasks completed. Routing to Output Finalizer.")
        return {
            "next_node": "OutputFinalizer"
        }
        
def orchestrator_router(state: AgentState):
    """Conditional edge function to map next_node to the actual node"""
    return state.get("next_node", "OutputFinalizer")
