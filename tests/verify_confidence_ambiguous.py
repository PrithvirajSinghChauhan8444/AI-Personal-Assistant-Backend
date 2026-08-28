import os
import sys
from dotenv import load_dotenv

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')), override=True)

from src.CoreFunctions.StateGraph.main_graph import app

def test_ambiguous_email():
    print("🚀 Running Live Ambiguity Task Routing Test (Ambiguity Expected)...")
    goal = "Send an email to John saying hello."

    initial_state = {
        "primary_goal": goal,
        "active_subtasks": [],
        "working_memory": {
            # Inject context containing multiple Johns to force ambiguity
            "user_profile": {
                "john_friend": "john.friend@example.com",
                "john_boss": "john.boss@example.com"
            },
            "relevant_memories": [
                "I have a friend named John.",
                "My boss is named John."
            ]
        },
        "completed_tasks": {},
        "final_response": "",
        "chat_history": []
    }

    config = {"configurable": {"thread_id": "manual_verify_confidence_ambiguity"}}

    print("\n--- Executing State Graph Flow ---")
    try:
        for event in app.stream(initial_state, config=config):
            for node_name, state_update in event.items():
                print(f"\n📍 Node '{node_name}' finished execution.")
                if node_name == "TaskRouter":
                    print("Task Router Plan:")
                    for st in state_update.get("active_subtasks", []):
                        print(f"  - [{st['id']}] Worker: {st['assigned_worker']} | Score: {st.get('confidence_score')}")
                        print(f"    Reason: {st.get('confidence_reason')}")
                        print(f"    Ref: {st.get('entity_reference')}")
                elif node_name == "Orchestrator":
                    print(f"  Next target: {state_update.get('next_node')}")
                elif node_name == "OutputFinalizer":
                    print("\n--- Conversational Output ---")
                    print(state_update.get("final_response"))
    except Exception as e:
        print(f"❌ Verification failed with error: {e}")

if __name__ == "__main__":
    test_ambiguous_email()
