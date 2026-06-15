import os
import sys
import json
from dotenv import load_dotenv

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')))

from src.CoreFunctions.StateGraph.main_graph import app

def run_test():
    print("🚀 Running Observability Logging System Verification Test...")
    
    # Session ID for this test run
    test_session_id = "test_logging_session"
    
    # Target paths
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    log_dir = os.path.join(base_dir, "Memory", "logs")
    session_log_path = os.path.join(log_dir, f"session_{test_session_id}.log")
    session_json_path = os.path.join(log_dir, f"session_{test_session_id}.json")
    latest_log_path = os.path.join(log_dir, "latest.log")
    latest_json_path = os.path.join(log_dir, "latest.json")
    
    # Remove existing files if they exist to start fresh
    for path in [session_log_path, session_json_path, latest_log_path, latest_json_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    # Initiate standard path or fast path query
    goal = "Remember my favorite_fruit is Mango"
    print(f"\n--- Initiating Graph Run: '{goal}' ---")
    
    initial_state = {
        "primary_goal": goal,
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": ""
    }
    
    config = {"configurable": {"thread_id": test_session_id}}
    
    try:
        # Wrap the turn execution in init/end logging just like main_graph.py interactive loop
        from src.CoreFunctions.logger import init_session_logger, end_session_logger
        init_session_logger(test_session_id, goal)
        
        # Execute stream
        for event in app.stream(initial_state, config=config):
            for node_name, state_update in event.items():
                print(f"[{node_name}] Executed.")
        
        state_data = app.get_state(config)
        final_resp = state_data.values.get("final_response", "")
        
        end_session_logger(final_resp, success=True)
        print(f"Final response synthesized: {final_resp}")
        
    except Exception as e:
        print(f"❌ Error during graph run: {e}")
        from src.CoreFunctions.logger import log_error, end_session_logger
        log_error("test_logging", str(e))
        end_session_logger("", success=False)
        
    # --- ASSERTS ---
    print("\n--- Verifying Log Files ---")
    
    # Check that logs folder was created and files exist
    assert os.path.exists(session_log_path), f"Session text log not found at {session_log_path}"
    assert os.path.exists(session_json_path), f"Session JSON log not found at {session_json_path}"
    assert os.path.exists(latest_log_path), f"Latest text log not found at {latest_log_path}"
    assert os.path.exists(latest_json_path), f"Latest JSON log not found at {latest_json_path}"
    print("✔ All 4 log files successfully created on disk.")
    
    # Read and verify JSON structure
    with open(session_json_path, "r", encoding="utf-8") as f:
        trace = json.load(f)
        
    assert trace["session_id"] == test_session_id, "Incorrect session_id in JSON trace"
    assert trace["primary_goal"] == goal, "Incorrect primary_goal in JSON trace"
    assert trace["success"] is True, "Session marked unsuccessful in JSON trace"
    assert len(trace["steps"]) > 0, "No execution steps recorded in JSON trace"
    print("✔ JSON trace contains valid schema and correctly tracked steps.")
    
    # Print a preview of the text log
    print("\n==================== TEXT LOG PREVIEW ====================")
    with open(session_log_path, "r", encoding="utf-8") as f:
        log_content = f.read()
        # Print first 1000 characters and last 1000 characters
        if len(log_content) > 2000:
            print(log_content[:1000])
            print("\n... [truncated log content] ...\n")
            print(log_content[-1000:])
        else:
            print(log_content)
    print("==========================================================")
    print("\n🎉 Observability Logging System verified successfully!")

if __name__ == "__main__":
    run_test()
