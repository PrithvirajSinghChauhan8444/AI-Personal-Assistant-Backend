from typing import Dict, List, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from modules.contracts.state_contract import AgentState
from modules.contracts.task_contract import WorkerCapability
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.task_router.router import TaskRouter
from modules.orchestrator.scheduler import TaskScheduler
from modules.synthesizer.finalizer import OutputSynthesizer
from modules.synthesizer.reflection import ReflectionEngine

def build_modular_pipeline(
    router: TaskRouter,
    scheduler: TaskScheduler,
    synthesizer: OutputSynthesizer,
    reflection: ReflectionEngine,
    workers: List[BaseWorkerProtocol]
):
    """Compiles the independent modules into a cohesive LangGraph workflow."""
    workflow = StateGraph(AgentState)

    # 1. Capabilities collection for router
    capabilities: List[WorkerCapability] = [
        WorkerCapability(
            name=w.name,
            description=w.description,
            routing_rules=w.routing_rules,
            categories=w.categories
        )
        for w in workers
    ]

    # 2. Add Nodes
    workflow.add_node("TaskRouter", lambda state: router.as_node(state, capabilities))
    workflow.add_node("Orchestrator", scheduler.as_node)

    for w in workers:
        if w.is_graph_node:
            workflow.add_node(w.name, w.execute)

    workflow.add_node("OutputFinalizer", synthesizer.as_node)
    workflow.add_node("Reflection", reflection.as_node)

    # 3. Add Edges
    workflow.set_entry_point("TaskRouter")
    workflow.add_edge("TaskRouter", "Orchestrator")

    # Routing map for conditional edges out of Orchestrator
    routing_map = {w.name: w.name for w in workers if w.is_graph_node}
    routing_map["OutputFinalizer"] = "OutputFinalizer"
    routing_map["Orchestrator"] = "Orchestrator"

    workflow.add_conditional_edges(
        "Orchestrator",
        scheduler.router_fn,
        routing_map
    )

    # Workers route back into Orchestrator
    for w in workers:
        if w.is_graph_node:
            workflow.add_edge(w.name, "Orchestrator")

    workflow.add_edge("OutputFinalizer", "Reflection")
    workflow.add_edge("Reflection", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
