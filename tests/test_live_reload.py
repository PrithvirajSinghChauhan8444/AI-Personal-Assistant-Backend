import os
import sys
import json

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.StateGraph.registry import WorkerRegistry, scan_and_register_workers
from src.CoreFunctions.StateGraph.main_graph import create_graph, SESSION_CONTEXT_PATH
from src.CoreFunctions.unified_memory import UnifiedMemory

def main():
    print("=========================================================")
    print("🔄 Live Reload Testing Tool")
    print("Keep this script running.")
    print("You can edit config/workers_config.json in another editor.")
    print("Press Enter to reload, or type 'exit' to quit.")
    print("=========================================================")

    # Initialize the Unified Memory cache singleton
    print("🧠 Initializing Unified Memory...")
    UnifiedMemory()

    while True:
        print("\n--- Current State ---")
        
        # 1. Force reload scanning and config syncing
        scan_and_register_workers(force_reload=True)
        
        # 2. Compile the graph dynamically
        app = create_graph()
        
        # 3. Load/read memory files like main_graph does
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
            except Exception as e:
                print(f"⚠️ Failed to read session context: {e}")

        # 4. Print results
        active_workers = WorkerRegistry.get_worker_names()
        print(f"✅ Active Workers in Registry: {', '.join(active_workers) if active_workers else '[None]'}")
        
        # Graph nodes
        graph_nodes = list(app.get_graph().nodes.keys())
        print(f"📊 Compiled Graph Nodes: {', '.join(graph_nodes)}")
        
        print(f"📖 Memory Loaded: {len(chat_history)} messages, {len(working_memory_init)} keys in working memory")

        try:
            cmd = input("\n[Press Enter to reload / type 'exit' to quit]: ").strip().lower()
            if cmd == "exit":
                print("👋 Goodbye!")
                break
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Goodbye!")
            break

if __name__ == "__main__":
    main()
