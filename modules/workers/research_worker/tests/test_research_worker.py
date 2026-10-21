import unittest
from unittest.mock import MagicMock
from modules.workers.research_worker.worker import ResearchWorker

class TestResearchWorker(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.worker = ResearchWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()

    def test_execute_research_success(self):
        msg_mock = MagicMock()
        msg_mock.content = "Research findings: Quantum computing algorithms have advanced in fault tolerance."
        self.worker._agent.invoke.return_value = {"messages": [msg_mock]}

        res = self.worker.execute_task("task_res_1", "Research quantum computing updates", {})
        self.assertEqual(res["status"], "completed")
        self.assertIn("Quantum computing", res["summary"])

    def test_execute_research_failure(self):
        self.worker._agent.invoke.side_effect = Exception("Search provider unreachable")
        res = self.worker.execute_task("task_res_1", "Research quantum computing updates", {})
        self.assertEqual(res["status"], "failed")
        self.assertIn("unreachable", res["error_message"])

if __name__ == "__main__":
    unittest.main()
