import os
import sys
from dotenv import load_dotenv

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')), override=True)

from src.CoreFunctions.StateGraph.main_graph import app

def run_test():
    print("🚀 Running StateGraph Search Integration Test...")
    print("\n--- Initiating Graph Run (Goal: Find the starting date of FIFA 2026) ---")
    
    initial_state = {
        "primary_goal": "tell me the fixtures of the fifa 26 world cup along the matches happening today.",
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": ""
    }
    
    config = {"configurable": {"thread_id": "test_search_flow_session"}}
    
    try:
        for event in app.stream(initial_state, config=config):
            for node_name, state_update in event.items():
                print(f"\n[{node_name}] Executed.")
                if node_name == "TaskRouter":
                    subtasks = state_update.get("active_subtasks", [])
                    print("  Parsed Subtasks:")
                    for idx, st in enumerate(subtasks, 1):
                        print(f"    {idx}. {st['assigned_worker']}: {st['description']}")
                elif node_name == "OutputFinalizer":
                    final_resp = state_update.get("final_response", "")
                    print(f"\n💬 Final Response:\n{final_resp}")
                    assert "June" in final_resp or "2026" in final_resp, "Expected response to mention the month of June or the year 2026"
                    print("\n✅ Integration Test Passed!")
    except Exception as e:
        print(f"❌ Error during graph run: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
