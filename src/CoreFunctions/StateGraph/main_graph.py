import os
import sys
from dotenv import load_dotenv

# Ensure proper path ops
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))) # Add src to path for 'Apps' and 'CoreFunctions' imports

# Load environment variables
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')), override=True)

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.CoreFunctions.StateGraph.state import AgentState
from src.CoreFunctions.StateGraph.task_router import task_router_node
from src.CoreFunctions.StateGraph.orchestrator import orchestrator_node, orchestrator_router
from src.CoreFunctions.StateGraph.workers import (
    system_worker_node, gmail_worker_node, 
    productivity_worker_node, memory_worker_node,
    classroom_worker_node, obsidian_worker_node, browser_worker_node,
    github_worker_node, misc_worker_node
)
from src.CoreFunctions.StateGraph.finalizer import output_finalizer_node
from src.CoreFunctions.StateGraph.memory_nodes import memory_injector_node, reflection_node
from src.CoreFunctions.unified_memory import UnifiedMemory

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
    # workflow.add_node("ObsidianWorker", obsidian_worker_node)
    workflow.add_node("BrowserWorker", browser_worker_node)
    workflow.add_node("GithubWorker", github_worker_node)
    workflow.add_node("MiscWorker", misc_worker_node)
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
            # "ObsidianWorker": "ObsidianWorker",
            "BrowserWorker": "BrowserWorker",
            "GithubWorker": "GithubWorker",
            "MiscWorker": "MiscWorker",
            "OutputFinalizer": "OutputFinalizer",
            "Orchestrator": "Orchestrator",
            "TaskRouter": "TaskRouter"
        }
    )
    
    # All workers route back to Orchestrator
    workflow.add_edge("SystemWorker", "Orchestrator")
    workflow.add_edge("GmailWorker", "Orchestrator")
    workflow.add_edge("ProductivityWorker", "Orchestrator")
    workflow.add_edge("MemoryWorker", "Orchestrator")
    workflow.add_edge("ClassroomWorker", "Orchestrator")
    # workflow.add_edge("ObsidianWorker", "Orchestrator")
    workflow.add_edge("BrowserWorker", "Orchestrator")
    workflow.add_edge("GithubWorker", "Orchestrator")
    workflow.add_edge("MiscWorker", "Orchestrator")
    
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

# Path for session context persistence
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SESSION_CONTEXT_PATH = os.path.join(BASE_DIR, "Memory", "session_context.json")
INTERRUPTED_TASK_PATH = os.path.join(BASE_DIR, "Memory", "interrupted_task.json")

def save_interrupted_task_checkpoint(state_values, status="running"):
    import json
    try:
        # Filter out transient keys from working memory to keep context clean
        transient_keys = ["active_skills", "skills_index", "user_profile", "relevant_memories", "fast_path_matched"]
        working_memory = state_values.get("working_memory", {}) or {}
        filtered_wm = {k: v for k, v in working_memory.items() if k not in transient_keys}

        data = {
            "status": status,
            "primary_goal": state_values.get("primary_goal", ""),
            "active_subtasks": state_values.get("active_subtasks", []),
            "working_memory": filtered_wm,
            "completed_tasks": state_values.get("completed_tasks", {}),
            "chat_history": state_values.get("chat_history", [])
        }
        
        # Integrate UnifiedMemory caching dump for crash recovery
        try:
            um = UnifiedMemory()
            if um.enabled:
                um_dump = {}
                for k in um.list_keys("*"):
                    mem = um.retrieve_memory(k)
                    if mem:
                        um_dump[k] = mem
                data["unified_memory_dump"] = um_dump
        except Exception as um_err:
            pass
        
        os.makedirs(os.path.dirname(INTERRUPTED_TASK_PATH), exist_ok=True)
        tmp_path = INTERRUPTED_TASK_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        
        # Atomic rename to prevent file corruption on power loss
        os.replace(tmp_path, INTERRUPTED_TASK_PATH)
    except Exception as e:
        print(f"\n  ⚠️ Failed to save interrupted task checkpoint: {e}", flush=True)

def clear_interrupted_task_checkpoint():
    try:
        if os.path.exists(INTERRUPTED_TASK_PATH):
            os.remove(INTERRUPTED_TASK_PATH)
    except Exception as e:
        print(f"\n  ⚠️ Failed to clear interrupted task checkpoint: {e}", flush=True)

def save_session_context_async(chat_history, working_memory, completed_tasks):
    def run_save():
        import json
        try:
            # 1. Filter out transient keys from working memory to keep context clean
            transient_keys = ["active_skills", "skills_index", "user_profile", "relevant_memories", "fast_path_matched"]
            filtered_wm = {k: v for k, v in working_memory.items() if k not in transient_keys}
            
            # 2. Save the raw context immediately (to ensure persistence even if summarization fails)
            context_data = {
                "chat_history": chat_history,
                "working_memory": filtered_wm,
                "completed_tasks": completed_tasks,
                "session_summary": working_memory.get("previous_session_summary", "")
            }
            
            # Integrate UnifiedMemory persistent keys archiving
            try:
                um = UnifiedMemory()
                if um.enabled:
                    um_persistent = {}
                    for k in um.list_keys("*"):
                        mem = um.retrieve_memory(k)
                        if mem and mem.get("persistent") == "yes":
                            um_persistent[k] = mem
                    context_data["unified_memory_persistent"] = um_persistent
            except Exception as um_err:
                print(f"⚠️ [UnifiedMemory] finalizer sync error: {um_err}")
            
            os.makedirs(os.path.dirname(SESSION_CONTEXT_PATH), exist_ok=True)
            with open(SESSION_CONTEXT_PATH, "w", encoding="utf-8") as f:
                json.dump(context_data, f, indent=4)
                
            # 3. Generate a quick summary of the conversation using Gemini
            if chat_history:
                from langchain_google_genai import ChatGoogleGenerativeAI
                from langchain_core.messages import SystemMessage, HumanMessage
                
                llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0)
                summary_prompt = """
                You are a context saver. Summarize the user's goals and what actions the assistant completed in this session in 2-3 concise sentences.
                Focus on outcomes: what files were created, what decisions were made, and what data was retrieved.
                Do not include system instructions or formatting tags. Keep it plain text.
                """
                
                history_str = ""
                for msg in chat_history[-6:]:  # summary of the last few turns
                    history_str += f"{msg['role']}: {msg['content']}\n"
                    
                response = llm.invoke([
                    SystemMessage(content=summary_prompt),
                    HumanMessage(content=f"History of recent turns:\n{history_str}")
                ])
                
                content = response.content
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            text_parts.append(item["text"])
                        elif isinstance(item, str):
                            text_parts.append(item)
                    summary_text = "".join(text_parts).strip()
                else:
                    summary_text = str(content).strip()
                
                # Update JSON with the new summary
                context_data["session_summary"] = summary_text
                with open(SESSION_CONTEXT_PATH, "w", encoding="utf-8") as f:
                    json.dump(context_data, f, indent=4)
                    
        except Exception as e:
            print(f"\n  ⚠️ Background Context Saver Error: {e}", flush=True)

    thread = threading.Thread(target=run_save, daemon=True)
    thread.start()

def print_node_header(node_name: str, timestamp: str):
    print(f"\nRunning {node_name} : ({timestamp})")
    print(f"--- {node_name} Finished ---")
    print(f"\n📍 Node '{node_name}' Output:")

def run_graph_execution(initial_state, config, thread_id, chat_history_list):
    """
    Executes the StateGraph stream with the given initial state and configuration.
    Saves checkpoints after each event for interruption recovery.
    """
    visualizer = CLIStatusVisualizer()
    visualizer.start("Analyzing request & decomposing into subtasks", "36") # Cyan

    try:
        from datetime import datetime
        for event in app.stream(initial_state, config=config):
            for node_name, state_update in event.items():
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                if node_name == "MemoryInjector":
                    visualizer.stop()
                    print_node_header(node_name, timestamp)
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
                    print_node_header(node_name, timestamp)
                    subtasks = state_update.get("active_subtasks", [])
                    print("-- PLAN:")
                    for idx, st in enumerate(subtasks, 1):
                        print(f"   {idx}. {st['assigned_worker']}: {st['description']}")
                    visualizer.start("Orchestrating subtasks", "34") # Blue
                
                elif node_name == "Orchestrator":
                    visualizer.stop()
                    next_node = state_update.get("next_node")
                    print_node_header(node_name, timestamp)
                    if next_node == "OutputFinalizer":
                        print("  -> All planned subtasks successfully completed. Routing to Output Finalizer.")
                    else:
                        subtasks = state_update.get("active_subtasks", [])
                        task_desc = ""
                        for st in subtasks:
                            if st["status"] == "in_progress":
                                task_desc = st['description']
                                break
                        
                        next_node_str = ", ".join(next_node) if isinstance(next_node, list) else next_node
                        print(f"  -> Next Node Target: {next_node_str} | Task: {task_desc}")
                        visualizer.start(f"Running {next_node_str}", "33") # Yellow
                
                elif node_name in ["SystemWorker", "GmailWorker", "ProductivityWorker", "MemoryWorker", "ClassroomWorker", "BrowserWorker", "GithubWorker", "MiscWorker"]:
                    visualizer.stop()
                    print_node_header(node_name, timestamp)
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

            # Save checkpoint after each graph event
            state_snapshot = app.get_state(config)
            save_interrupted_task_checkpoint(state_snapshot.values, status="running")
        
        # Retrieve latest state from checkpointer to save for multi-turn conversational persistence
        state_data = app.get_state(config)
        final_resp = state_data.values.get("final_response", "")
        
        # Trigger Asynchronous Background Self-Reflection (Phase 1 Optimization)
        if final_resp and state_data.values.get("completed_tasks"):
            state_snapshot = dict(state_data.values)
            def run_background_reflection(snap):
                try:
                    from src.CoreFunctions.logger import set_thread_session_id
                    set_thread_session_id(thread_id)
                    reflection_node(snap)
                except Exception as ex:
                    try:
                        log_path = os.path.join(BASE_DIR, "Memory", "reflection.log")
                        os.makedirs(os.path.dirname(log_path), exist_ok=True)
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(f"\nBackground Reflection Error: {ex}\n")
                    except Exception:
                        pass
            
            bg_thread = threading.Thread(target=run_background_reflection, args=(state_snapshot,), daemon=True)
            bg_thread.start()
        
        # Append exchange to local history
        chat_history_list.append({"role": "user", "content": initial_state["primary_goal"]})
        if final_resp:
            chat_history_list.append({"role": "assistant", "content": final_resp})
            
        # Keep history to last 10 messages (5 turns) for token safety
        if len(chat_history_list) > 10:
            chat_history_list[:] = chat_history_list[-10:]
            
        # Update working memory and completed tasks for local persistence across turns
        working_memory_latest = state_data.values.get("working_memory", {})
        completed_tasks_latest = state_data.values.get("completed_tasks", {})
        
        # Trigger Asynchronous Background Context Saver
        save_session_context_async(chat_history_list, working_memory_latest, completed_tasks_latest)
        
        # Clear recovery file since the execution succeeded!
        clear_interrupted_task_checkpoint()

        # End logging session successfully
        from src.CoreFunctions.logger import end_session_logger
        end_session_logger(final_resp, success=True)
        
        return working_memory_latest, completed_tasks_latest
        
    except Exception as e:
        visualizer.stop()
        print(f"❌ Execution Error: {e}")
        from src.CoreFunctions.logger import log_error, end_session_logger
        log_error("main_graph", str(e))
        end_session_logger("", success=False)
        raise e

def process_request_interactive():
    import json
    # Check for missing/placeholder API key
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        print("\n\033[1;31m⚠️  Gemini API Key Required\033[0m")
        print("Please configure the \033[1;36m.env\033[0m file in the project root directory with a valid Google Gemini API Key.")
        print("Format: \033[1;33mGEMINI_API_KEY=your_actual_api_key\033[0m")
        print("You can get a free key from Google AI Studio: \033[4;34mhttps://aistudio.google.com/\033[0m\n")
        return

    print("🤖 \033[1;32mAgent Manager (Dynamic State-Graph)\033[0m - Type 'exit' to quit.")
    
    # Initialize the Unified Memory cache singleton
    UnifiedMemory()

    # Load session context on startup
    chat_history = []
    working_memory_init = {}
    completed_tasks_init = {}
    if os.path.exists(SESSION_CONTEXT_PATH):
        try:
            with open(SESSION_CONTEXT_PATH, "r", encoding="utf-8") as f:
                context = json.load(f)
                chat_history = context.get("chat_history", [])
                working_memory_init = context.get("working_memory", {})
                completed_tasks_init = context.get("completed_tasks", {})
                previous_summary = context.get("session_summary", "")
                
                print(f"📖 Loaded {len(chat_history)} previous conversation exchanges.")
                if previous_summary:
                    working_memory_init["previous_session_summary"] = previous_summary
                    print(f"📝 Previous Session Summary: {previous_summary}")
                    
                # Restore UnifiedMemory persistent cache keys on startup
                um_persistent = context.get("unified_memory_persistent", {})
                if um_persistent:
                    try:
                        um = UnifiedMemory()
                        if um.enabled:
                            for k, mem in um_persistent.items():
                                um.store_memory(
                                    k, 
                                    mem, 
                                    sharable=(mem.get("sharable") == "yes"), 
                                    persistent=True
                                )
                            print(f"⚡ [UnifiedMemory] Restored {len(um_persistent)} persistent keys from session context.")
                    except Exception as um_err:
                        print(f"⚠️ [UnifiedMemory] startup restore failed: {um_err}")
        except Exception as e:
            print(f"⚠️ Failed to load previous session context: {e}")
            
    # Check for recovery of an interrupted task on startup
    if os.path.exists(INTERRUPTED_TASK_PATH):
        try:
            with open(INTERRUPTED_TASK_PATH, "r", encoding="utf-8") as f:
                recovered_task = json.load(f)
            
            goal = recovered_task.get("primary_goal", "")
            subtasks = recovered_task.get("active_subtasks", [])
            
            if goal:
                print(f"\n\033[1;33m⚠️  An interrupted task was detected from your last session!\033[0m")
                print(f"   Goal: \"{goal}\"")
                if subtasks:
                    print("   Status of subtasks:")
                    for st in subtasks:
                        status_symbol = "✔" if st["status"] == "completed" else "⏳"
                        print(f"     [{status_symbol}] {st['assigned_worker']}: {st['description']}")
                else:
                    print("   (The task was interrupted before subtasks were planned.)")
                
                print("\033[1;31m(Warning: Resuming may re-execute tasks that were interrupted mid-process)\033[0m")
                
                while True:
                    choice = input("\nWould you like to (c)ontinue/resume this task, or (e)end/discard it? [c/e]: ").strip().lower()
                    if choice in ['c', 'continue','r']:
                        print(f"\n🔄 Resuming task: \"{goal}\"")
                        
                        import uuid
                        thread_id = f"session_{uuid.uuid4().hex[:8]}"
                        config = {"configurable": {"thread_id": thread_id}}
                        
                        # Restore UnifiedMemory cache keys on task recovery
                        um_dump = recovered_task.get("unified_memory_dump", {})
                        if um_dump:
                            try:
                                um = UnifiedMemory()
                                if um.enabled:
                                    for k, mem in um_dump.items():
                                        um.store_memory(
                                            k, 
                                            mem, 
                                            sharable=(mem.get("sharable") == "yes"), 
                                            persistent=(mem.get("persistent") == "yes")
                                        )
                                    print(f"⚡ [UnifiedMemory] Restored {len(um_dump)} cache keys from recovery checkpoint.")
                            except Exception as um_err:
                                print(f"⚠️ [UnifiedMemory] recovery restore failed: {um_err}")
                                
                        # Initialize recovered state
                        initial_state = {
                            "primary_goal": goal,
                            "active_subtasks": subtasks,
                            "working_memory": recovered_task.get("working_memory", {}),
                            "completed_tasks": recovered_task.get("completed_tasks", {}),
                            "final_response": "",
                            "chat_history": recovered_task.get("chat_history", chat_history)
                        }
                        
                        from src.CoreFunctions.logger import init_session_logger
                        init_session_logger(thread_id, f"Resuming: {goal}")
                        
                        try:
                            working_memory_init, completed_tasks_init = run_graph_execution(
                                initial_state, config, thread_id, chat_history
                            )
                        except KeyboardInterrupt:
                            print("\n👋 Execution interrupted again. State saved.")
                            sys.exit(0)
                        except Exception:
                            # Error printed in run_graph_execution
                            pass
                        break
                        
                    elif choice in ['e', 'end', 'discard']:
                        print("🗑️ Interrupted task discarded.")
                        clear_interrupted_task_checkpoint()
                        break
                    else:
                        print("Invalid choice. Please enter 'c' to resume or 'e' to end/discard.")
                        
        except json.JSONDecodeError:
            print("⚠️ Detected a corrupted recovery file. Starting fresh...")
            clear_interrupted_task_checkpoint()
        except Exception as e:
            print(f"⚠️ Failed to process recovery of interrupted task: {e}")
            clear_interrupted_task_checkpoint()

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

        import uuid
        thread_id = f"session_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "primary_goal": user_input,
            "active_subtasks": [],
            "working_memory": working_memory_init,
            "completed_tasks": completed_tasks_init,
            "final_response": "",
            "chat_history": chat_history
        }

        # Immediately save initial checkpoint as "initializing"
        save_interrupted_task_checkpoint(initial_state, status="initializing")

        # Initialize session logger for execution tracing
        from src.CoreFunctions.logger import init_session_logger
        init_session_logger(thread_id, user_input)

        try:
            working_memory_init, completed_tasks_init = run_graph_execution(
                initial_state, config, thread_id, chat_history
            )
        except KeyboardInterrupt:
            print("\n👋 Execution interrupted. State saved.")
            sys.exit(0)
        except Exception:
            # Error printed in run_graph_execution
            pass

if __name__ == "__main__":
    process_request_interactive()
