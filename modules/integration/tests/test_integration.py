import unittest
from unittest.mock import MagicMock
from modules.contracts.state_contract import AgentState
from modules.contracts.task_contract import TaskPlan, SubTaskModel, WorkerCapability
from modules.task_router.router import TaskRouter
from modules.orchestrator.scheduler import TaskScheduler
from modules.synthesizer.finalizer import OutputSynthesizer
from modules.synthesizer.reflection import ReflectionEngine
from modules.workers.system_worker.worker import SystemWorker
from modules.integration.pipeline_builder import build_modular_pipeline

class TestModularIntegrationPipeline(unittest.TestCase):
    def setUp(self):
        # Mock LLMs for fast, offline, deterministic testing
        self.mock_llm = MagicMock()
        
        # Router mock
        self.structured_llm_mock = MagicMock()
        self.mock_llm.with_structured_output.return_value = self.structured_llm_mock
        self.structured_llm_mock.invoke.return_value = TaskPlan(
            primary_goal="Check system diagnostics",
            subtasks=[
                SubTaskModel(
                    id="task_1",
                    description="Get system health",
                    assigned_worker="SystemWorker",
                    depends_on=[],
                    confidence_score=1.0,
                    confidence_reason="Diagnostics"
                )
            ]
        )

        # Worker mock
        self.worker = SystemWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()
        resp_msg = MagicMock()
        resp_msg.content = "System health is 100% nominal."
        self.worker._agent.invoke.return_value = {"messages": [resp_msg]}

        # Finalizer & Reflection mock
        finalizer_mock_resp = MagicMock()
        finalizer_mock_resp.content = "All checks passed. System is nominal."
        self.mock_llm.invoke.return_value = finalizer_mock_resp

        self.router = TaskRouter(llm_client=self.mock_llm)
        self.scheduler = TaskScheduler(allow_parallel=False)
        self.synthesizer = OutputSynthesizer(llm_client=self.mock_llm)
        self.reflection = ReflectionEngine(llm_client=self.mock_llm)

        # Build pipeline
        self.app = build_modular_pipeline(
            router=self.router,
            scheduler=self.scheduler,
            synthesizer=self.synthesizer,
            reflection=self.reflection,
            workers=[self.worker]
        )

    def test_full_pipeline_execution(self):
        initial_state: AgentState = {
            "primary_goal": "Check system diagnostics",
            "active_subtasks": [],
            "working_memory": {},
            "completed_tasks": {},
            "final_response": "",
            "error_logs": []
        }
        config = {"configurable": {"thread_id": "test_thread_1"}}
        
        # Execute stream
        events = list(self.app.stream(initial_state, config=config))
        self.assertTrue(len(events) > 0)

        # Check end state
        state_data = self.app.get_state(config)
        self.assertIn("nominal", state_data.values.get("final_response", ""))
        self.assertEqual(len(state_data.values.get("completed_tasks", {})), 1)

if __name__ == "__main__":
    unittest.main()
