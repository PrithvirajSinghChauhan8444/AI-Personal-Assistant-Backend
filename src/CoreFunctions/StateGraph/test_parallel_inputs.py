import os
import sys
import time
import threading
from unittest.mock import patch

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import targets
from src.CoreFunctions.auth_utils import verify_password
from src.CoreFunctions.tools import search_skills_tool, request_human_intervention_sync
from src.CoreFunctions.vector_memory import rebuild_skills_vector_store

def test_skills_vector_store():
    print("Testing Skills Vector Store indexing & semantic search...")
    # Rebuild
    rebuild_skills_vector_store()
    
    # Test search_skills_tool (password-free)
    # Search for something related to email or general queries
    res = search_skills_tool("send email or fetch mail", count=1)
    print("Search Result Preview:")
    print(res)
    
    # Assert
    assert "Error" not in res, "Failed search skills tool execution"
    print("✔ Skills Vector Store & search_skills_tool test passed!")


def dummy_worker_thread(worker_name, task_desc, trigger_type, results_list):
    """Simulates a running worker executing _run_ephemeral_agent to test stack introspection."""
    def _run_ephemeral_agent(w_name, t_desc):
        # Local variables to match stack introspection
        worker_name = w_name
        task_desc = t_desc
        
        # Add a delay to increase likelihood of collision if synchronization isn't working
        time.sleep(0.1)
        
        if trigger_type == "PASSWORD":
            auth_ok = verify_password()
            results_list.append((w_name, "PASSWORD", auth_ok))
        else:
            resp = request_human_intervention_sync("Need 2FA authentication code")
            results_list.append((w_name, "INTERVENTION", resp))
            
    _run_ephemeral_agent(worker_name, task_desc)


def test_parallel_stdin_serialization():
    print("\nTesting parallel stdin serialization and introspection...")
    
    # Get the actual password to pass verification
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    env_paths = [
        os.path.join(base_dir, ".env"),
        os.path.join(base_dir, "config", ".env")
    ]
    correct_password = None
    for env_path in env_paths:
        if os.path.exists(env_path):
            for encoding in ['utf-8', 'utf-16', 'utf-8-sig', 'cp1252']:
                try:
                    with open(env_path, 'r', encoding=encoding) as f:
                        for line in f:
                            stripped = line.strip()
                            if stripped.startswith("SYSTEM_PASSWORD="):
                                correct_password = stripped.split("=", 1)[1].strip().strip("'").strip('"')
                                break
                            elif stripped.startswith("AGENT_PASSWORD="):
                                correct_password = stripped.split("=", 1)[1].strip().strip("'").strip('"')
                                break
                    if correct_password is not None:
                        break
                except Exception:
                    continue
            if correct_password is not None:
                break
                
    actual_pwd = correct_password or "test_assistant_pwd"
    if not correct_password:
        os.environ["SYSTEM_PASSWORD"] = actual_pwd
    
    inputs_called = []
    
    def mock_input(prompt_text):
        thread_name = threading.current_thread().name
        inputs_called.append((thread_name, time.time()))
        print(f"[{thread_name}] Mock input prompt shown: '{prompt_text.strip()}'")
        # Give a small sleep to simulate typing delay
        time.sleep(0.5)
        # Return correct password if prompt is for password, or custom code if intervention
        if "Password" in prompt_text:
            return actual_pwd
        return "123456"
        
    with patch("builtins.input", side_effect=mock_input):
        results = []
        threads = [
            threading.Thread(target=dummy_worker_thread, name="WorkerThread-Gmail", args=("GmailWorker", "Retrieve email details for billing", "PASSWORD", results)),
            threading.Thread(target=dummy_worker_thread, name="WorkerThread-Browser", args=("BrowserWorker", "Complete checkout form", "INTERVENTION", results))
        ]
        
        # Start both threads concurrently
        for t in threads:
            t.start()
            
        # Join threads
        for t in threads:
            t.join()
            
        print("\nResults:", results)
        print("Input Calls:", inputs_called)
        
        # Verification: Assert inputs did not overlap
        # Check timestamps. If they were parallel without lock, their mock_input blocks would overlap.
        # Since each call takes 0.5s, if they are serialized, the start time of the second call must be
        # at least 0.5s after the start of the first call.
        assert len(inputs_called) == 2, "Both prompts should have been called"
        t1, t2 = inputs_called[0][1], inputs_called[1][1]
        time_diff = abs(t2 - t1)
        print(f"Time difference between inputs: {time_diff:.4f} seconds")
        assert time_diff >= 0.45, "Inputs did not run sequentially!"
        print("✔ Parallel stdin inputs serialized successfully!")


if __name__ == "__main__":
    test_skills_vector_store()
    test_parallel_stdin_serialization()
