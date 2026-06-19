import os
import sys
import uuid
from dotenv import load_dotenv

# Set paths to src and root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Load .env file
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')), override=True)

from src.CoreFunctions.unified_memory import UnifiedMemory
from src.CoreFunctions.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.vector_memory import store_vector, delete_vector_fact, search_vector
from src.CoreFunctions.StateGraph.main_graph import app

def run_test():
    print("=" * 60)
    print("🧪 Unified Memory & Worker Access Verification Test")
    print("=" * 60)

    # 1. Generate unique test values to ensure no cached/legacy data confusion
    test_id = uuid.uuid4().hex[:6].upper()
    test_key = f"verification_token"
    test_value = f"SECRET-TOKEN-{test_id}"
    
    vector_fact = f"The verification code for the hermes database test is CODE-{test_id}."

    # Initialize memory
    UnifiedMemory()

    print(f"\n📥 [Step 1] Storing mock data directly into Unified Memory...")
    print(f"   -> Storing key-value: '{test_key}' = '{test_value}' (category: 'user')")
    store_memory("user", test_key, test_value)
    
    print(f"   -> Storing semantic fact to Vector DB: \"{vector_fact}\"")
    store_vector(vector_fact)

    print("\n🔍 [Step 2] Verifying store success via direct python calls...")
    direct_fetch = fetch_memory("user", test_key)
    print(f"   -> Direct fetch_memory('{test_key}') returned: '{direct_fetch}'")
    
    direct_search = search_vector(f"hermes database test verification code", k=1)
    print(f"   -> Direct search_vector returned: {direct_search}")

    print("\n🚀 [Step 3] Launching State Graph execution to see if Workers retrieve this...")
    # The query mentions terms matching both the personal profile keywords (triggers user_profile retrieval)
    # and the semantic vector facts query terms.
    query = f"Retrieve my verification_token and my hermes database test verification code."
    print(f"   -> User Query: \"{query}\"")
    
    initial_state = {
        "primary_goal": query,
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": "",
        "chat_history": []
    }
    
    thread_id = f"test_verify_{test_id.lower()}"
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Run graph and inspect what node outputs
        for event in app.stream(initial_state, config=config):
            for node_name, state_update in event.items():
                print(f"\n📍 [Node Finished] {node_name}")
                
                # Check MemoryInjector node output to see what details are injected into state
                if node_name == "MemoryInjector":
                    wm = state_update.get("working_memory", {}) or {}
                    user_profile = wm.get("user_profile", {})
                    relevant_memories = wm.get("relevant_memories", [])
                    
                    print(f"   --- Injected Context Details ---")
                    print(f"   Injected User Profile: {user_profile}")
                    print(f"   Injected Vector Memories: {relevant_memories}")
                    
                    if test_key in user_profile and user_profile[test_key] == test_value:
                        print("   ✅ SUCCESS: Key-value verified in injected user_profile context!")
                    else:
                        print("   ❌ FAILURE: Key-value missing from injected user_profile context!")
                        
                    fact_found = any(vector_fact in mem for mem in relevant_memories)
                    if fact_found or any(f"CODE-{test_id}" in mem for mem in relevant_memories):
                        print("   ✅ SUCCESS: Fact verified in injected vector memories context!")
                    else:
                        print("   ❌ FAILURE: Fact missing from injected vector memories context!")
                
                elif node_name == "OutputFinalizer":
                    # Display response
                    final_resp = state_update.get("final_response", "")
                    print(f"   --- Final Response ---")
                    print(final_resp)
                    print(f"   ----------------------")
                    
                    if test_value in final_resp and f"CODE-{test_id}" in final_resp:
                        print("   🏆 VERDICT: Success! The workers successfully accessed, read, and outputted the correct memory values.")
                    else:
                        print("   ⚠️ WARNING: The values were injected, but the worker response did not explicitly use/print both. Check the prompt wording.")
                        
    except Exception as e:
        print(f"❌ Error during execution: {e}")

    finally:
        # 4. Clean up test data
        print("\n🗑️ [Step 4] Cleaning up verification mock data from memory systems...")
        try:
            delete_memory("user", test_key)
            delete_vector_fact(vector_fact)
            print("   -> Cleanup completed successfully.")
        except Exception as e:
            print(f"   ⚠️ Cleanup failed: {e}")
            
    print("=" * 60)

if __name__ == "__main__":
    run_test()
