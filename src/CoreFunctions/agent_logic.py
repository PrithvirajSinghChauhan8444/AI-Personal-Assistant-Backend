import os
import sys

# Ensure src is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from langchain_core.messages import HumanMessage
from src.CoreFunctions.LangGraph.main_graph import app

def process_command(user_input: str, history=None) -> str:
    """
    Bridge function that routes incoming user chat commands to the LangGraph Multi-Agent Orchestrator.
    Auto-approves the planner's output for non-interactive API requests.
    """
    if not app:
        return "❌ Error: The LangGraph Multi-Agent Orchestrator failed to initialize."

    # Establish thread configuration for state persistence
    config = {"configurable": {"thread_id": "api_server_default_session"}}

    # Formulate input state
    initial_input = {"messages": [HumanMessage(content=user_input)]}

    try:
        # 1. Run the graph. If it has a Planner node, it will pause after the Planner step.
        state = app.invoke(initial_input, config=config)

        # 2. Check if the graph is currently paused (e.g., at the Planner verification interrupt)
        snapshot = app.get_state(config)
        if snapshot.next:
            # For the API server/non-interactive context, we auto-approve and resume execution
            state = app.invoke(None, config=config)

        # 3. Retrieve final response
        final_response = state.get("final_response", "")
        if not final_response:
            # Fallback: extract from last message
            messages = state.get("messages", [])
            if messages:
                final_response = messages[-1].content

        return final_response

    except Exception as e:
        print(f"❌ LangGraph API Bridge Error: {e}")
        return f"Error executing request via LangGraph: {str(e)}"
