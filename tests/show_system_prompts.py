import os
import sys

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.StateGraph.registry import WorkerRegistry, scan_and_register_workers
from src.CoreFunctions.StateGraph.task_router import get_router_prompt
from src.CoreFunctions.StateGraph.executor import THINKING_INSTRUCTION, HUMAN_INTERVENTION_INSTRUCTION, _load_worker_skills

def main():
    print("==================================================")
    print("🔍 Scanning and registering workers...")
    scan_and_register_workers()
    print("==================================================")

    # 1. Print Task Router Prompt
    print("\n🤖 === TASK ROUTER SYSTEM PROMPT ===")
    print(get_router_prompt())
    print("==================================================")

    # 2. Print Active Workers and their Prompts
    print("\n🚀 === ACTIVE WORKER PROMPTS ===")
    active_workers = WorkerRegistry.get_all_workers()
    
    if not active_workers:
        print("[No active workers found in configuration]")
        return
        
    for name, worker in sorted(active_workers.items()):
        print(f"\n❇️ Worker Name: {name}")
        print(f"   Exposed to Router (is_graph_node): {worker.is_graph_node}")
        print("--------------------------------------------------")
        
        # Base System Prompt used in compile_worker_agents
        base_prompt = worker.instructions + THINKING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION
        print("   --- SYSTEM PROMPT (Instructions + HITL + Formatting Rules) ---")
        print(base_prompt)
        print("--------------------------------------------------")
        
        # Runtime Prompt Layout (template) used during execution
        stable_guideline = (
            "IMPORTANT NOTE ON LARGE DATA:\n"
            "If any entry in the Working Memory contains a `\"__file_reference__\"`, the actual large data has "
            "been saved to that local file path to avoid context bloat. You can directly read the content of "
            "that file using your file-reading tools (like `read_file_tool` or running python/terminal commands), "
            "copy/move the file, or use the file path as an attachment/input for other tools."
        )
        
        skills_str = _load_worker_skills(name)
        skills_section = ""
        if skills_str:
            skills_section = (
                f"\n\n### Specialized Skills for {name}:\n"
                f"Use the following step-by-step procedures when resolving tasks in your domain:\n"
                f"{skills_str}"
            )
            
        print("   --- RUNTIME INPUT PROMPT TEMPLATE ---")
        print(f"{stable_guideline}{skills_section}")
        print("\n   [Runtime Volatile Inputs]")
        print("   ### Operational Context (Volatile):")
        print("   Task: <task description>")
        print("   Working Memory (Data from previous tasks): { ... }")
        print("==================================================")

if __name__ == "__main__":
    main()
