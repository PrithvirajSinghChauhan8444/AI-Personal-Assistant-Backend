import os
import sys

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.StateGraph.worker_framework import WorkerRegistry, scan_and_register_workers
from src.CoreFunctions.StateGraph.task_router import get_router_prompt
from src.CoreFunctions.StateGraph.executor import _build_worker_system_prompt, _load_worker_skills

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
        base_prompt = _build_worker_system_prompt(name, worker)
        print("   --- SYSTEM PROMPT (Two-Tier: Domain Rules + General Directives + Invariants) ---")
        print(base_prompt)
        print("--------------------------------------------------")
        
        # Runtime Prompt Layout (template) used during execution
        skills_str = _load_worker_skills(name)
        skills_section = ""
        if skills_str:
            skills_section = (
                f"\n### Specialized Skills for {name}:\n"
                f"Use the following step-by-step procedures when resolving tasks in your domain:\n"
                f"{skills_str}\n"
            )
            
        print("   --- RUNTIME INPUT PROMPT TEMPLATE ---")
        if skills_section:
            print(skills_section)
        print("   ### Operational Context:")
        print("   Task: <task description>")
        print("   Working Memory (Data from previous tasks): { ... }")
        print("==================================================")

if __name__ == "__main__":
    main()
