import os
import sys
from dotenv import load_dotenv

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')))

from src.CoreFunctions.StateGraph.main_graph import app
from src.CoreFunctions.memory import store_memory

def test_pipeline():
    print("🚀 Initiating Advanced Features Verification Test...")
    
    # 1. Store mock profile memories
    store_memory("user", "favorite_city", "Dehradun")
    store_memory("user", "brother_name", "Rohan")
    
    # Define conversational history
    chat_history = [
        {"role": "user", "content": "What is the weather in Agra?"},
        {"role": "assistant", "content": "The weather in Agra is sunny and 35 degrees."}
    ]
    
    print("\n--- TEST 1: Multi-Turn Conversation Routing ---")
    print("Query: 'Email it to my brother Rohan'")
    
    initial_state_1 = {
        "primary_goal": "Email it to my brother Rohan",
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": "",
        "chat_history": chat_history
    }
    
    config = {"configurable": {"thread_id": "test_multi_turn"}}
    
    try:
        for event in app.stream(initial_state_1, config=config):
            for node_name, state_update in event.items():
                if node_name == "TaskRouter":
                    print(f"[{node_name}] Decomposed subtasks:")
                    subtasks = state_update.get("active_subtasks", [])
                    for st in subtasks:
                        print(f"  - [{st['assigned_worker']}] {st['description']}")
    except Exception as e:
        print(f"❌ Test 1 Error: {e}")
        
    print("\n--- TEST 2: Web Search Integration ---")
    print("Query: 'Search the web for the latest releases of Google Gemini models'")
    
    initial_state_2 = {
        "primary_goal": "Search the web for the latest releases of Google Gemini models",
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": "",
        "chat_history": []
    }
    
    try:
        for event in app.stream(initial_state_2, config=config):
            for node_name, state_update in event.items():
                if node_name == "TaskRouter":
                    print(f"[{node_name}] Decomposed subtasks:")
                    subtasks = state_update.get("active_subtasks", [])
                    for st in subtasks:
                        print(f"  - [{st['assigned_worker']}] {st['description']}")
                elif node_name == "SystemWorker":
                    print(f"[{node_name}] Executed web search tool successfully.")
    except Exception as e:
        print(f"❌ Test 2 Error: {e}")

if __name__ == "__main__":
    test_pipeline()
