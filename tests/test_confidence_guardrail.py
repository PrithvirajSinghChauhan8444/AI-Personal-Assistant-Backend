import os
import sys

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.StateGraph.orchestrator import orchestrator_node

def run_test():
    print("🚀 Running Orchestrator Confidence Guardrail Test...")

    # Mock AgentState with a low-confidence subtask
    mock_state = {
        "primary_goal": "Delete my folder",
        "active_subtasks": [
            {
                "id": "task_1",
                "description": "Delete the user's folder",
                "assigned_worker": "SystemWorker",
                "status": "pending",
                "depends_on": [],
                "confidence_score": 0.65,
                "confidence_reason": "The folder path was not named in the prompt and multiple directories match in the workspace.",
                "entity_reference": "vector_memory:path_fact"
            }
        ],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": "",
        "chat_history": []
    }

    print("\n--- Executing Orchestrator Node with Mock State ---")
    result = orchestrator_node(mock_state)

    print("\nOrchestrator Result:")
    print(f"next_node: {result.get('next_node')}")
    print(f"final_response:\n{result.get('final_response')}")
    
    # Assertions
    assert result.get("next_node") == "OutputFinalizer", "Should route to OutputFinalizer on low confidence!"
    assert "I stopped executing your request because I am not sure about the context:" in result.get("final_response"), "Should include the clarification reason in final response!"
    
    # Verify tasks are marked as failed
    for t in result.get("active_subtasks", []):
        assert t["status"] == "failed", f"Task {t['id']} should be aborted/failed!"
        
    print("\n✅ Confidence Guardrail Test Passed Successfully!")

if __name__ == "__main__":
    run_test()
