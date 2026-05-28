import os
import sys
from dotenv import load_dotenv

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')))

from src.CoreFunctions.StateGraph.main_graph import app
from src.CoreFunctions.memory import store_memory
from src.CoreFunctions.vector_memory import store_vector

def run_test():
    print("🚀 Running StateGraph Memory Pipeline Test...")
    
    # 1. Store some initial mock memories to vector and JSON memory
    store_memory("user", "mail", "testing_user@example.com")
    store_memory("user", "favorite_city", "Dehradun")
    store_vector("The user has a brother named Rohan.")
    store_vector("The user prefers using Python for scripting.")
    
    print("\n--- Initiating Graph Run: 'Tell Rohan I will email him later' ---")
    
    # Run the graph with a query that triggers the memory match
    initial_state = {
        "primary_goal": "Tell Rohan I will email him later",
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": ""
    }
    
    config = {"configurable": {"thread_id": "test_session"}}
    
    # Execute the graph
    try:
        for event in app.stream(initial_state, config=config):
            for node_name, state_update in event.items():
                print(f"[{node_name}] Executed.")
                if node_name == "MemoryInjector":
                    wm = state_update.get("working_memory", {})
                    print(f"  -> Injected Profile: {wm.get('user_profile')}")
                    print(f"  -> Injected Memories: {wm.get('relevant_memories')}")
                elif node_name == "TaskRouter":
                    subtasks = state_update.get("active_subtasks", [])
                    print("  -> Planned Subtasks:")
                    for st in subtasks:
                        print(f"     - [{st['assigned_worker']}] {st['description']}")
    except Exception as e:
        print(f"❌ Error during graph run: {e}")

if __name__ == "__main__":
    run_test()
