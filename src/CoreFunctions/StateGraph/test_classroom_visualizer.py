import os
import sys
from dotenv import load_dotenv

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')))

from src.CoreFunctions.StateGraph.main_graph import app

def run_test():
    print("🚀 Running Classroom Coursework Canvas Visualizer Integration Test...")

    initial_state = {
        "primary_goal": "Fetch my Google Classroom courses and coursework, and then create a beautiful visual mind-map Canvas diagram of my academic courses, assignments, and deadlines inside my Obsidian vault.",
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": "",
        "chat_history": []
    }

    config = {"configurable": {"thread_id": "classroom_canvas_test"}}

    try:
        for event in app.stream(initial_state, config=config):
            for node_name, state_update in event.items():
                print(f"\n📍 Node '{node_name}' finished execution.")
                if node_name == "TaskRouter":
                    print("Decomposed Subtasks:")
                    for st in state_update.get("active_subtasks", []):
                        print(f"  - [{st['assigned_worker']}] {st['description']}")
                elif node_name == "Orchestrator":
                    next_node = state_update.get("next_node")
                    print(f"  -> Next Node: {next_node}")
                elif node_name == "ClassroomWorker":
                    print("ClassroomWorker completed execution.")
                elif node_name == "ObsidianWorker":
                    print("ObsidianWorker completed execution.")
    except Exception as e:
        print(f"❌ Error during graph run: {e}")

if __name__ == "__main__":
    run_test()
