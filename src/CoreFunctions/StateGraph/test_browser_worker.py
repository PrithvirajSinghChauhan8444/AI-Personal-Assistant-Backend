import os
import sys
from dotenv import load_dotenv

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')), override=True)

# Print configuration diagnostic
import os
print(f"🔍 [Config Debug] BROWSER_HEADLESS={os.getenv('BROWSER_HEADLESS')}")
print(f"🔍 [Config Debug] BROWSER_SLOW_MO={os.getenv('BROWSER_SLOW_MO')}")

from src.CoreFunctions.StateGraph.main_graph import app

def run_test():
    print("🚀 Running StateGraph BrowserWorker Integration Test...")
    print("\n--- Initiating Graph Run: 'Navigate to https://example.com and read the page structure' ---")
    
    initial_state = {
        "primary_goal": "Navigate to https://example.com and read the page structure to tell me what headings or links are there.",
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": ""
    }
    
    config = {"configurable": {"thread_id": "test_browser_session"}}
    
    # Execute the graph
    try:
        for event in app.stream(initial_state, config=config):
            for node_name, state_update in event.items():
                print(f"\n[{node_name}] Executed.")
                if node_name == "TaskRouter":
                    subtasks = state_update.get("active_subtasks", [])
                    print("  Parsed Subtasks:")
                    for idx, st in enumerate(subtasks, 1):
                        print(f"    {idx}. {st['assigned_worker']}: {st['description']}")
                elif node_name == "BrowserWorker":
                    print("  BrowserWorker finished successfully.")
                elif node_name == "OutputFinalizer":
                    final_resp = state_update.get("final_response", "")
                    print(f"\n💬 Final Response:\n{final_resp}")
    except Exception as e:
        print(f"❌ Error during graph run: {e}")

if __name__ == "__main__":
    run_test()
