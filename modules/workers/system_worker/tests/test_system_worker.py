import unittest
from unittest.mock import MagicMock
from modules.workers.system_worker.worker import SystemWorker

class TestSystemWorker(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        # Mock react agent responses
        self.worker = SystemWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()

    def test_execute_task_success(self):
        msg_mock = MagicMock()
        msg_mock.content = "CPU usage is 22% and memory is optimal."
        self.worker._agent.invoke.return_value = {"messages": [msg_mock]}

        res = self.worker.execute_task("task_1", "Check system health", {})
        self.assertEqual(res["status"], "completed")
        self.assertIn("22%", res["summary"])

    def test_execute_task_failure_handling(self):
        self.worker._agent.invoke.side_effect = Exception("Tool failure")
        res = self.worker.execute_task("task_1", "Invalid action", {})
        self.assertEqual(res["status"], "failed")
        self.assertIn("Tool failure", res["error_message"])

if __name__ == "__main__":
    unittest.main()
