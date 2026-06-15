import os
import sys
from dotenv import load_dotenv

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')), override=True)

from src.CoreFunctions.StateGraph.main_graph import app

def run_test(prompt, thread_id):
    print(f"\n🚀 Running StateGraph Custom Skills Test for: '{prompt}'...")
    
    initial_state = {
        "primary_goal": prompt,
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": ""
    }
    
    config = {"configurable": {"thread_id": thread_id}}
    
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
                elif node_name == "OutputFinalizer":
                    final_resp = state_update.get("final_response", "")
                    print(f"\n💬 Final Response:\n{final_resp}")
    except Exception as e:
        print(f"❌ Error during graph run: {e}")

if __name__ == "__main__":
    # Test 1: YouTube Music status check
    run_test("Check the status of my YouTube Music playback", "test_ytmusic_status")
    
    # Test 2: Spotify playback control
    run_test("Toggle play/pause on my Spotify player", "test_spotify_toggle")
    
    # Test 3: Miscellaneous API task
    run_test("List all my playlists on YouTube Music", "test_misc_ytmusic_playlists")
