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
    productivity_worker_node, memory_worker_node,
    classroom_worker_node, obsidian_worker_node, browser_worker_node
)
from src.CoreFunctions.StateGraph.finalizer import output_finalizer_node
from src.CoreFunctions.StateGraph.memory_nodes import memory_injector_node, reflection_node

def memory_injector_router(state: AgentState):
    working_memory = state.get("working_memory", {}) or {}
    if working_memory.get("fast_path_matched", False):
        return "OutputFinalizer"
    return "TaskRouter"

def create_graph():
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("MemoryInjector", memory_injector_node)
    workflow.add_node("TaskRouter", task_router_node)
    workflow.add_node("Orchestrator", orchestrator_node)
    workflow.add_node("SystemWorker", system_worker_node)
    workflow.add_node("GmailWorker", gmail_worker_node)
    workflow.add_node("ProductivityWorker", productivity_worker_node)
    workflow.add_node("MemoryWorker", memory_worker_node)
    workflow.add_node("ClassroomWorker", classroom_worker_node)
    workflow.add_node("ObsidianWorker", obsidian_worker_node)
    workflow.add_node("BrowserWorker", browser_worker_node)
    workflow.add_node("OutputFinalizer", output_finalizer_node)
    workflow.add_node("Reflection", reflection_node)
    
    # Set Entry Point
    workflow.set_entry_point("MemoryInjector")
    
    # Memory Injector routes to OutputFinalizer (Fast-Path Bypass) or TaskRouter (Standard Path)
    workflow.add_conditional_edges(
        "MemoryInjector",
        memory_injector_router,
        {
            "OutputFinalizer": "OutputFinalizer",
            "TaskRouter": "TaskRouter"
        }
    )
    
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
            "ClassroomWorker": "ClassroomWorker",
            "ObsidianWorker": "ObsidianWorker",
            "BrowserWorker": "BrowserWorker",
            "OutputFinalizer": "OutputFinalizer",
            "Orchestrator": "Orchestrator"
        }
    )
    
    # All workers route back to Orchestrator
    workflow.add_edge("SystemWorker", "Orchestrator")
    workflow.add_edge("GmailWorker", "Orchestrator")
    workflow.add_edge("ProductivityWorker", "Orchestrator")
    workflow.add_edge("MemoryWorker", "Orchestrator")
    workflow.add_edge("ClassroomWorker", "Orchestrator")
    workflow.add_edge("ObsidianWorker", "Orchestrator")
    workflow.add_edge("BrowserWorker", "Orchestrator")
    
    # OutputFinalizer completes the user-facing graph synchronously
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
    instance = None

    def __init__(self):
        import builtins
        builtins.active_cli_visualizer = self
        CLIStatusVisualizer.instance = self
        self.active = False
        self.thread = None
        self.status_text = ""
        self.color_code = "34"  # Default to blue
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.lock = threading.Lock()
        self.is_paused = False

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
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                text = self.status_text
                color = self.color_code
                if len(text) > 55:
                    text = text[:52] + "..."
            
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
    
    chat_history = []
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
            "final_response": "",
            "chat_history": chat_history
        }

        # Initialize and start visualizer
        visualizer = CLIStatusVisualizer()
        visualizer.start("Analyzing request & decomposing into subtasks", "36") # Cyan
        
        try:
            from datetime import datetime
            for event in app.stream(initial_state, config=config):
                for node_name, state_update in event.items():
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    if node_name == "MemoryInjector":
                        visualizer.stop()
                        print(f"\nRunning MemoryInjector : ({timestamp})")
                        print("--- MemoryInjector Finished ---")
                        print("\n📍 Node 'MemoryInjector' Output:")
                        wm = state_update.get("working_memory", {}) or {}
                        
                        if wm.get("fast_path_matched", False):
                            print("  ⚡ [Fast-Path Bypass] Matched fast-path intent! Resolving instantly...")
                        else:
                            user_profile = wm.get("user_profile", {})
                            relevant_memories = wm.get("relevant_memories", [])
                            if user_profile:
                                print(f"  -> Loaded User Profile keys: {list(user_profile.keys())}")
                            if relevant_memories:
                                print(f"  -> Injected {len(relevant_memories)} semantically relevant memories.")
                            visualizer.start("Analyzing request & decomposing into subtasks", "36")
                    
                    elif node_name == "TaskRouter":
                        visualizer.stop()
                        print(f"\nRunning TaskRouter : ({timestamp})")
                        print("--- TaskRouter Finished ---")
                        print("\n📍 Node 'TaskRouter' Output:")
                        subtasks = state_update.get("active_subtasks", [])
                        print("-- PLAN:")
                        for idx, st in enumerate(subtasks, 1):
                            print(f"   {idx}. {st['assigned_worker']}: {st['description']}")
                        visualizer.start("Orchestrating subtasks", "34") # Blue
                    
                    elif node_name == "Orchestrator":
                        visualizer.stop()
                        next_node = state_update.get("next_node")
                        print(f"\nRunning Orchestrator : ({timestamp})")
                        print("--- Orchestrator Finished ---")
                        print("\n📍 Node 'Orchestrator' Output:")
                        if next_node == "OutputFinalizer":
                            print("  -> All planned subtasks successfully completed. Routing to Output Finalizer.")
                        else:
                            subtasks = state_update.get("active_subtasks", [])
                            task_desc = ""
                            for st in subtasks:
                                if st["status"] == "in_progress":
                                    task_desc = st['description']
                                    break
                            print(f"  -> Next Node Target: {next_node} | Task: {task_desc}")
                            visualizer.start(f"Running {next_node}", "33") # Yellow
                    
                    elif node_name in ["SystemWorker", "GmailWorker", "ProductivityWorker", "MemoryWorker", "ClassroomWorker", "BrowserWorker"]:
                        visualizer.stop()
                        print(f"\nRunning {node_name} : ({timestamp})")
                        print(f"--- {node_name} Finished ---")
                        print(f"\n📍 Node '{node_name}' Output:")
                        subtasks = state_update.get("active_subtasks", [])
                        completed_desc = ""
                        for st in subtasks:
                            if st["status"] == "completed":
                                completed_desc = st["description"]
                        if completed_desc:
                            print(f"  \033[1;32m✔\033[0m Completed Task: {completed_desc}")
                        else:
                            print(f"  \033[1;32m✔\033[0m {node_name} completed execution successfully.")
                        visualizer.start("Evaluating next steps", "34") # Blue
                        
                    elif node_name == "OutputFinalizer":
                        visualizer.stop()
            
            # Retrieve latest state from checkpointer to save for multi-turn conversational persistence
            state_data = app.get_state(config)
            final_resp = state_data.values.get("final_response", "")
            
            # Trigger Asynchronous Background Self-Reflection (Phase 1 Optimization)
            if final_resp:
                state_snapshot = dict(state_data.values)
                def run_background_reflection(snap):
                    try:
                        reflection_node(snap)
                    except Exception as ex:
                        print(f"\n  ⚠️ Background Reflection Error: {ex}")
                
                bg_thread = threading.Thread(target=run_background_reflection, args=(state_snapshot,), daemon=True)
                bg_thread.start()
            
            # Append exchange to local history
            chat_history.append({"role": "user", "content": user_input})
            if final_resp:
                chat_history.append({"role": "assistant", "content": final_resp})
                
            # Keep history to last 10 messages (5 turns) for token safety
            if len(chat_history) > 10:
                chat_history = chat_history[-10:]
        except Exception as e:
            visualizer.stop()
            print(f"❌ Execution Error: {e}")

if __name__ == "__main__":
    process_request_interactive()
