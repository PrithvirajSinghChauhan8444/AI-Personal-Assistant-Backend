from typing import List
from modules.contracts.task_contract import WorkerCapability

def build_task_router_prompt(available_workers: List[WorkerCapability]) -> str:
    worker_bullets = []
    rules = []
    for w in available_workers:
        worker_bullets.append(f"- **{w.name}**: {w.description}")
        if w.routing_rules:
            rules.extend(w.routing_rules)

    workers_str = "\n".join(worker_bullets) if worker_bullets else "- Default Worker"
    rules_str = "\n".join([f"{idx+1}. {r}" for idx, r in enumerate(rules)])

    return f"""You are the Task Router. Decompose the user request into isolated subtasks formatted strictly according to the TaskPlan schema.

Available Workers:
{workers_str}

Routing Rules:
{rules_str}

1. Decompose the goal into sequential or parallel subtasks.
2. If task B depends on output from task A, specify `depends_on = [task A ID]`. If independent, keep `depends_on = []`.
3. Only assign tasks to the workers listed above.
"""
