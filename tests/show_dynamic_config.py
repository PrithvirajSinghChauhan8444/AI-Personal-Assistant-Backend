import os
import sys

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.StateGraph.registry import WorkerRegistry, scan_and_register_workers

def main():
    print("==================================================")
    print("🔍 Scanning and registering workers...")
    scan_and_register_workers()
    print("==================================================")

    print("\n📋 1. ALL REGISTERED WORKERS:")
    for name, worker in sorted(WorkerRegistry._registry.items()):
        node_type = "Graph Node" if worker.is_graph_node else "Sub-Worker"
        print(f"  - {name} ({node_type})")

    print("\n✅ 2. CURRENTLY ACTIVE WORKERS (from config):")
    active_workers = WorkerRegistry.get_all_workers()
    for name, worker in sorted(active_workers.items()):
        node_type = "Graph Node" if worker.is_graph_node else "Sub-Worker"
        print(f"  - {name} ({node_type})")

    print("\n📝 3. COMPILED Router workers_list_str:")
    worker_descriptions = []
    for name, worker in active_workers.items():
        if worker.is_graph_node:
            worker_descriptions.append(f"- {name}: {worker.description}")
            
    workers_list_str = "\n".join(worker_descriptions)
    print("--------------------------------------------------")
    print(workers_list_str if workers_list_str else "[No active graph-node workers found]")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()
