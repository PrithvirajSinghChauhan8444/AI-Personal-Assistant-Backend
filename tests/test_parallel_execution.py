import os
import sys
from dotenv import load_dotenv

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')))

from src.CoreFunctions.StateGraph.main_graph import app

def run_test():
    print("🚀 Running Parallel DAG Branching Worker Execution Test...")

    # A prompt containing independent tasks to trigger parallel branching
    goal = "Fetch my unread emails from Gmail, check the weather in San Francisco, and get my system memory stats concurrently in parallel."

    initial_state = {
        "primary_goal": goal,
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": "",
        "chat_history": []
    }

    config = {"configurable": {"thread_id": "parallel_execution_test"}}

    try:
        print("\n--- Starting State-Graph Flow ---")
        for event in app.stream(initial_state, config=config):
            for node_name, state_update in event.items():
                print(f"\n📍 Node '{node_name}' finished execution.")
                if node_name == "TaskRouter":
                    print("Decomposed Subtasks & Dependencies:")
                    for st in state_update.get("active_subtasks", []):
                        print(f"  - [{st['id']}] Assigned to: {st['assigned_worker']} | Depends on: {st.get('depends_on', [])}")
                        print(f"    Description: {st['description']}")
                elif node_name == "Orchestrator":
                    next_node = state_update.get("next_node")
                    print(f"  -> Orchestrator state evaluation complete. Next: {next_node}")
                elif node_name == "OutputFinalizer":
                    print("\n--- Finalized Conversational Response ---")
                    print(state_update.get("final_response", ""))
                    
    except Exception as e:
        print(f"❌ Error during graph run: {e}")

if __name__ == "__main__":
    run_test()
