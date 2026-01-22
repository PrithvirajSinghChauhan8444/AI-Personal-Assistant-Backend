import os
import sys
from typing import TypedDict, Annotated, Sequence
import operator

# Ensure proper path ops
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))) # Add src to path for 'Apps' and 'CoreFunctions' imports

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.CoreFunctions.LangGraph.logger import GraphLogger

# Import the manager node configuration
try:
    from src.CoreFunctions.LangGraph.manager_declare import manager_node, MEMBERS
except ImportError:
    # Fallback for dev if imports fail
    manager_node = None
    MEMBERS = []

try:
    from src.CoreFunctions.LangGraph.worker_declare import worker_nodes
except ImportError:
    worker_nodes = {}

try:
    from src.CoreFunctions.LangGraph.output_finaliser import output_finaliser_node
except ImportError:
    output_finaliser_node = None

try:
    from src.CoreFunctions.LangGraph.planner_declare import planner_node
except ImportError:
    planner_node = None

# ==========================================
# 1. STATE DEFINITION
# ==========================================
class AgentState(TypedDict):
    # The list of messages in the conversation
    # operator.add ensures that new messages are appended, not overwritten
    messages: Annotated[Sequence[BaseMessage], operator.add]
    # The 'next' field records which agent should act next
    next: str
    final_response: str # The final response from the manager/finaliser

# ==========================================
# 2. GRAPH CONSTRUCTION
# ==========================================
def create_graph():
    if not manager_node:
        print("❌ Error: Manager Node not initialized (Install langchain_groq?)")
        return None

    workflow = StateGraph(AgentState)

    # Add the Manager Node
    workflow.add_node("Manager", manager_node)
    
    # Add Worker Nodes
    for name, node in worker_nodes.items():
        workflow.add_node(name, node)
    
    # Add Output Finaliser Node
    if output_finaliser_node:
        workflow.add_node("output_finaliser", output_finaliser_node)

    # Add Planner Node
    if planner_node:
        print("✅ Planner Node Initialized")
        workflow.add_node("Planner", planner_node)
        workflow.set_entry_point("Planner")
        workflow.add_edge("Planner", "Manager")
    else:
        print("⚠️ Planner Node Missing - Starting with Manager")
        workflow.set_entry_point("Manager")

    # Define Conditional Edges
    # The manager outputs {"next": "..."}
    # We map that output to the next node.
    # Since we ONLY have the Manager right now, we map everything to END
    # but we print what would have happened for debugging.
    
    
    
    conditional_map = {k: k for k in MEMBERS if k in worker_nodes} # Route to actual worker if exists
    # For members not implemented yet, we can keep them pointing to END or handle gracefully
    # conditional_map["FINISH"] = END
    # Route FINISH to output_finaliser
    conditional_map["FINISH"] = "output_finaliser"

    def route_logic(state):
        next_agent = state.get("next")
        GraphLogger.log_decision("Router", str(next_agent))
        return next_agent

    workflow.add_conditional_edges(
        "Manager",
        route_logic,
        conditional_map
    )
    
    # Add Edges from Workers back to Manager
    for name in worker_nodes:
        workflow.add_edge(name, "Manager")
    
    # Add Edge from Finaliser to END
    workflow.add_edge("output_finaliser", END)

    # Add checkpointer for persistence (required for interrupts)
    memory = MemorySaver()

    # Compile with interrupt after Planner to allow user verification
    return workflow.compile(
        checkpointer=memory,
        interrupt_after=["Planner"] if planner_node else []
    )

# ==========================================
# 3. EXECUTION INTERFACE
# ==========================================
app = create_graph()

def process_request_interactive():
    print("🤖 Agent Manager (LangGraph) - Type 'exit' to quit.")
    
    if not app:
        print("❌ Graph failed to compile.")
        return

    # Initialize empty history
    chat_history = []

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("👋 Goodbye!")
            break

        if not user_input:
            continue

        # Config for state persistence
        thread_id = "interactive_session"
        config = {"configurable": {"thread_id": thread_id}}

        # Create the initial state
        initial_input = {"messages": [HumanMessage(content=user_input)]}

        print("... Processing ...")
        
        # Function to run the graph stream
        def run_stream(input_data):
            try:
                for event in app.stream(input_data, config=config):
                    for key, value in event.items():
                        print(f"\n📍 Node '{key}' Output:")
                        
                        # Pretty print message content if available
                        if "messages" in value:
                            for msg in value["messages"]:
                                if hasattr(msg, "content"):
                                    print(f"-- {msg.content}")

                        # Check for final_response to display nicely
                        if "final_response" in value and value["final_response"]:
                            print(f"\n💬 Manager says: {value['final_response']}")
            except Exception as e:
                print(f"❌ Execution Error: {e}")

        # 1. Run until interrupt or finish
        run_stream(initial_input)

        # 2. Check if we are paused at Planner (Verification Step)
        snapshot = app.get_state(config)
        if snapshot.next:
            # We are paused. Check if it's after Planner.
            # (In this simple graph, interrupt_after=['Planner'] is the only pause)
            print("\n✋ Plan Created. Waiting for approval.")
            
            # The plan is in the last message of the state
            # (We could print it again here if needed, but it was just printed by the stream)
            
            choice = input(">> Approve Plan? (y/n): ").strip().lower()
            
            if choice == 'y':
                print("✅ Plan Approved. Resuming execution...")
                # Resume with None (continues from current state)
                run_stream(None)
            else:
                print("❌ Plan Rejected. Aborting.")
                # We could potentially add logic to edit the plan or loop back, 
                # but for now we stop. The usage loop continues so user can try again.

if __name__ == "__main__":
    process_request_interactive()
