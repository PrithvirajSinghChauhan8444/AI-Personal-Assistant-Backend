import os
import sys
from dotenv import load_dotenv

# Ensure proper path ops
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))) # Add src to path for 'Apps' and 'CoreFunctions' imports

# Load environment variables
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')))

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.CoreFunctions.StateGraph.state import AgentState
from src.CoreFunctions.StateGraph.task_router import task_router_node
from src.CoreFunctions.StateGraph.orchestrator import orchestrator_node, orchestrator_router
from src.CoreFunctions.StateGraph.workers import (
    system_worker_node, gmail_worker_node, 
    productivity_worker_node, memory_worker_node
)
from src.CoreFunctions.StateGraph.finalizer import output_finalizer_node

def create_graph():
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("TaskRouter", task_router_node)
    workflow.add_node("Orchestrator", orchestrator_node)
    workflow.add_node("SystemWorker", system_worker_node)
    workflow.add_node("GmailWorker", gmail_worker_node)
    workflow.add_node("ProductivityWorker", productivity_worker_node)
    workflow.add_node("MemoryWorker", memory_worker_node)
    workflow.add_node("OutputFinalizer", output_finalizer_node)
    
    # Set Entry Point
    workflow.set_entry_point("TaskRouter")
    
    # Task Router goes to Orchestrator
    workflow.add_edge("TaskRouter", "Orchestrator")
    
    # Orchestrator conditionally routes based on the 'next_node' in state
    workflow.add_conditional_edges(
        "Orchestrator",
        orchestrator_router,
        {
            "SystemWorker": "SystemWorker",
            "GmailWorker": "GmailWorker",
            "ProductivityWorker": "ProductivityWorker",
            "MemoryWorker": "MemoryWorker",
            "OutputFinalizer": "OutputFinalizer"
        }
    )
    
    # All workers route back to Orchestrator
    workflow.add_edge("SystemWorker", "Orchestrator")
    workflow.add_edge("GmailWorker", "Orchestrator")
    workflow.add_edge("ProductivityWorker", "Orchestrator")
    workflow.add_edge("MemoryWorker", "Orchestrator")
    
    # OutputFinalizer ends the graph
    workflow.add_edge("OutputFinalizer", END)
    
    # Checkpointer for state persistence
    memory = MemorySaver()
    
    # Compile Graph
    return workflow.compile(checkpointer=memory)

# Execute
app = create_graph()

import time
import threading

class CLIStatusVisualizer:
    def __init__(self):
        self.active = False
        self.thread = None
        self.status_text = ""
        self.color_code = "34"  # Default to blue
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.lock = threading.Lock()

    def start(self, text="Processing", color="34"):
        with self.lock:
            self.status_text = text
            self.color_code = color
            if self.active:
                return
            self.active = True
            self.thread = threading.Thread(target=self._animate, daemon=True)
            self.thread.start()

    def update(self, text, color=None):
        with self.lock:
            self.status_text = text
            if color:
                self.color_code = color

    def stop(self):
        with self.lock:
            if not self.active:
                return
            self.active = False
        if self.thread:
            self.thread.join()
        # Clear line fully
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def _animate(self):
        i = 0
        while True:
            with self.lock:
                if not self.active:
                    break
                text = self.status_text
                color = self.color_code
            
            frame = self.spinner_frames[i % len(self.spinner_frames)]
            sys.stdout.write(f"\r\033[K\033[1;{color}m{frame}\033[0m \033[37m{text}...\033[0m")
            sys.stdout.flush()
            time.sleep(0.08)
            i += 1

def process_request_interactive():
    # Check for missing/placeholder API key
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        print("\n\033[1;31m⚠️  Gemini API Key Required\033[0m")
        print("Please configure the \033[1;36m.env\033[0m file in the project root directory with a valid Google Gemini API Key.")
        print("Format: \033[1;33mGEMINI_API_KEY=your_actual_api_key\033[0m")
        print("You can get a free key from Google AI Studio: \033[4;34mhttps://aistudio.google.com/\033[0m\n")
        return

    print("🤖 \033[1;32mAgent Manager (Dynamic State-Graph)\033[0m - Type 'exit' to quit.")
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Goodbye!")
            break
            
        if user_input.lower() in ["exit", "quit"]:
            print("👋 Goodbye!")
            break

        if not user_input:
            continue

        # Fast-Path Semantic Router for pure greetings/chit-chat
        GREETINGS = {"hi", "hello", "hey", "howdy", "hola", "yo", "greetings", "good morning", "good afternoon", "good evening"}
        clean_input = "".join(c for c in user_input.lower() if c.isalnum() or c.isspace()).strip()
        if clean_input in GREETINGS:
            from langchain_google_genai import ChatGoogleGenerativeAI
            print("\n\033[1;35m🤖 Assistant:\033[0m ", end="", flush=True)
            fast_llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.7)
            try:
                for chunk in fast_llm.stream(f"The user said '{user_input}'. Respond with a friendly, short greeting and ask how you can help today."):
                    if chunk.content:
                        text_chunk = ""
                        if isinstance(chunk.content, str):
                            text_chunk = chunk.content
                        elif isinstance(chunk.content, list):
                            for item in chunk.content:
                                if isinstance(item, dict) and "text" in item:
                                    text_chunk += item["text"]
                                elif isinstance(item, str):
                                    text_chunk += item
                        print(text_chunk, end="", flush=True)
                print("\n")
            except Exception:
                print("Hi there! How can I assist you today?\n")
            continue

        thread_id = "interactive_session"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "primary_goal": user_input,
            "active_subtasks": [],
            "working_memory": {},
            "completed_tasks": {},
            "final_response": ""
        }

        # Initialize and start visualizer
        visualizer = CLIStatusVisualizer()
        visualizer.start("Analyzing request & decomposing into subtasks", "36") # Cyan
        
        try:
            for event in app.stream(initial_state, config=config):
                for node_name, state_update in event.items():
                    if node_name == "TaskRouter":
                        visualizer.stop()
                        print("\n📋 \033[1;36mDecomposed Task Plan:\033[0m")
                        subtasks = state_update.get("active_subtasks", [])
                        for st in subtasks:
                            print(f"  \033[32m├─\033[0m [\033[1;33m{st['assigned_worker']}\033[0m] {st['description']}")
                        print()
                        visualizer.start("Orchestrating subtasks", "34") # Blue
                    
                    elif node_name == "Orchestrator":
                        next_node = state_update.get("next_node")
                        if next_node == "OutputFinalizer":
                            visualizer.stop()
                            print("✨ All subtasks successfully executed. Synthesizing response...")
                        else:
                            subtasks = state_update.get("active_subtasks", [])
                            task_desc = ""
                            for st in subtasks:
                                if st["status"] == "in_progress":
                                    task_desc = f": {st['description']}"
                                    break
                            visualizer.update(f"Running {next_node}{task_desc}", "33") # Yellow
                    
                    elif node_name in ["SystemWorker", "GmailWorker", "ProductivityWorker", "MemoryWorker"]:
                        visualizer.stop()
                        subtasks = state_update.get("active_subtasks", [])
                        completed_desc = ""
                        for st in subtasks:
                            if st["status"] == "completed":
                                completed_desc = st["description"]
                        if completed_desc:
                            print(f"  \033[1;32m✔\033[0m Completed: {completed_desc}")
                        else:
                            print(f"  \033[1;32m✔\033[0m {node_name} finished execution.")
                        visualizer.start("Evaluating next steps", "34") # Blue
                        
                    elif node_name == "OutputFinalizer":
                        visualizer.stop()
        except Exception as e:
            visualizer.stop()
            print(f"❌ Execution Error: {e}")

if __name__ == "__main__":
    process_request_interactive()
