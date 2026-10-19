import unittest
from unittest.mock import MagicMock
from modules.contracts.task_contract import TaskPlan, SubTaskModel, WorkerCapability
from modules.task_router.router import TaskRouter

class TestTaskRouter(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.structured_llm_mock = MagicMock()
        self.mock_llm.with_structured_output.return_value = self.structured_llm_mock
        self.router = TaskRouter(llm_client=self.mock_llm)

    def test_route_successful_plan(self):
        expected_plan = TaskPlan(
            primary_goal="Check unread emails and summarize them",
            subtasks=[
                SubTaskModel(
                    id="task_1",
                    description="Fetch unread emails",
                    assigned_worker="GmailWorker",
                    depends_on=[],
                    confidence_score=1.0,
                    confidence_reason="Email query"
                ),
                SubTaskModel(
                    id="task_2",
                    description="Summarize the emails",
                    assigned_worker="SystemWorker",
                    depends_on=["task_1"],
                    confidence_score=0.9,
                    confidence_reason="File/summary task"
                )
            ]
        )
        self.structured_llm_mock.invoke.return_value = expected_plan

        capabilities = [
            WorkerCapability(name="GmailWorker", description="Email operations"),
            WorkerCapability(name="SystemWorker", description="System actions")
        ]
        plan = self.router.route("Check unread emails and summarize them", capabilities)

        self.assertEqual(len(plan.subtasks), 2)
        self.assertEqual(plan.subtasks[0].assigned_worker, "GmailWorker")
        self.assertEqual(plan.subtasks[1].depends_on, ["task_1"])

    def test_route_fallback_on_error(self):
        self.structured_llm_mock.invoke.side_effect = Exception("LLM connection timed out")
        capabilities = [WorkerCapability(name="SystemWorker", description="System operations")]
        
        plan = self.router.route("Check status", capabilities)
        self.assertEqual(len(plan.subtasks), 1)
        self.assertEqual(plan.subtasks[0].assigned_worker, "SystemWorker")
        self.assertIn("Fallback", plan.subtasks[0].confidence_reason)

if __name__ == "__main__":
    unittest.main()
