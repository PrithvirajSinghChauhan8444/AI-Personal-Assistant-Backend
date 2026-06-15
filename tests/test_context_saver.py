import os
import sys

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.StateGraph.main_graph import save_session_context_async
import time

chat_history = [
    {"role": "user", "content": "hello"},
    {"role": "assistant", "content": "hi there!"}
]
working_memory = {
    "previous_session_summary": "Initial summary"
}
completed_tasks = {}

print("Triggering background context saver...")
save_session_context_async(chat_history, working_memory, completed_tasks)

print("Waiting for background task to complete...")
time.sleep(5)
print("Done.")
