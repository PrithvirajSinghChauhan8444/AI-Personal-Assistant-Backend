import os
import uuid
from typing import Dict, Any, List, Optional

from modules.contracts.state_contract import AgentState
from modules.task_router.router import TaskRouter
from modules.orchestrator.scheduler import TaskScheduler
from modules.synthesizer.finalizer import OutputSynthesizer
from modules.synthesizer.reflection import ReflectionEngine
from modules.workers.system_worker.worker import SystemWorker
from modules.workers.communication_worker.worker import CommunicationWorker
from modules.workers.productivity_worker.worker import ProductivityWorker
from modules.infrastructure.observability.logger import ModuleLogger
from modules.infrastructure.storage.unified_storage import UnifiedStorage
from modules.integration.pipeline_builder import build_modular_pipeline

class ApplicationOrchestrator:
    """The Final Integration Module.
    Wires all decoupled modules into the end-to-end conversational flow,
    manages execution streams, session checkpoints, and state persistence.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.storage = UnifiedStorage()
        self.logger = ModuleLogger()

        # Initialize decoupled cognitive modules
        self.router = TaskRouter()
        self.scheduler = TaskScheduler(allow_parallel=True)
        self.synthesizer = OutputSynthesizer()
        self.reflection = ReflectionEngine()

        # Instantiate workers
        self.workers = [
            SystemWorker(),
            CommunicationWorker(),
            ProductivityWorker()
        ]

        # Compile full graph
        self.pipeline = build_modular_pipeline(
            router=self.router,
            scheduler=self.scheduler,
            synthesizer=self.synthesizer,
            reflection=self.reflection,
            workers=self.workers
        )

    def run(self, user_prompt: str, thread_id: Optional[str] = None) -> str:
        """Executes the complete request lifecycle across all independent modules."""
        thread_id = thread_id or f"session_{uuid.uuid4().hex[:8]}"
        run_config = {"configurable": {"thread_id": thread_id}}

        self.logger.log_event("ApplicationOrchestrator", "session_start", {
            "thread_id": thread_id,
            "goal": user_prompt
        })

        initial_state: AgentState = {
            "primary_goal": user_prompt,
            "active_subtasks": [],
            "working_memory": {},
            "completed_tasks": {},
            "final_response": "",
            "error_logs": []
        }

        final_response = ""
        try:
            for event in self.pipeline.stream(initial_state, config=run_config):
                for node_name, state_update in event.items():
                    self.logger.log_event(node_name, "node_transition", state_update)

            state_snapshot = self.pipeline.get_state(run_config)
            final_response = state_snapshot.values.get("final_response", "")

            self.logger.log_event("ApplicationOrchestrator", "session_complete", {
                "thread_id": thread_id,
                "final_response": final_response
            })
        except Exception as e:
            self.logger.log_event("ApplicationOrchestrator", "session_error", {
                "error": str(e)
            })
            final_response = f"An execution error occurred: {e}"

        return final_response
