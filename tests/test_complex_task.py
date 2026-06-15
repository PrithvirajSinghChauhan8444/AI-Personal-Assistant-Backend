import os
import sys
import threading
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')), override=True)

from src.CoreFunctions.StateGraph.main_graph import create_graph, CLIStatusVisualizer

app = create_graph()

def test_run():
    user_input = "fetch my 5 most recent emails from Gmail, check my system's CPU and RAM health metrics, and save a small 200 word greeting message locally then send me all this to my college mail also tell me all the fifa world cup matches going to happen in the next 24hr including the one going on currently with the results of the completed ones"
    
    import uuid
    thread_id = f"session_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "primary_goal": user_input,
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": "",
        "chat_history": []
    }

    # Initialize and start visualizer
    visualizer = CLIStatusVisualizer()
    visualizer.start("Analyzing request & decomposing into subtasks", "36")
    
    try:
        for event in app.stream(initial_state, config=config):
            for node_name, state_update in event.items():
                if node_name == "Orchestrator":
                    visualizer.stop()
                    next_node = state_update.get("next_node")
                    print(f"📍 Orchestrator Next: {next_node}")
                    visualizer.start(f"Running {next_node}", "33")
                elif node_name in ["TaskRouter", "OutputFinalizer"] or "Worker" in node_name:
                    visualizer.stop()
                    print(f"✅ Node Finished: {node_name}")
                    visualizer.start("Evaluating next steps", "34")
                    
        state_data = app.get_state(config)
        final_resp = state_data.values.get("final_response", "")
        visualizer.stop()
        print(f"\nFinal Response:\n{final_resp}")
        
    except Exception as e:
        visualizer.stop()
        print(f"❌ Execution Error: {e}")

if __name__ == "__main__":
    test_run()
