import os
import sys
from dotenv import load_dotenv

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')), override=True)

print(f"🔍 [Config Debug] GEMINI_MODEL={os.getenv('GEMINI_MODEL')}")
print(f"🔍 [Config Debug] BROWSER_HEADLESS={os.getenv('BROWSER_HEADLESS')}")
print(f"🔍 [Config Debug] BROWSER_SLOW_MO={os.getenv('BROWSER_SLOW_MO')}")

from src.CoreFunctions.StateGraph.main_graph import app

def run_test():
    print("🚀 Running Complex GitHub Browser Integration Test...")
    
    initial_state = {
        "primary_goal": (
            "Go to github.com, search for 'agentic automation', open any matching repository, "
            "look at its contributors list, open one of the contributors' profile pages, and return "
            "that contributor's repositories and basic profile/info."
        ),
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": ""
    }
    
    config = {"configurable": {"thread_id": "test_github_complex_session"}}
    
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
                    print("  BrowserWorker completed subtasks.")
                elif node_name == "OutputFinalizer":
                    final_resp = state_update.get("final_response", "")
                    print(f"\n💬 Final Response:\n{final_resp}")
    except Exception as e:
        print(f"❌ Error during complex github test run: {e}")

if __name__ == "__main__":
    run_test()
