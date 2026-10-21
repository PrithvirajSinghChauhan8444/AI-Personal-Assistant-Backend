import unittest
from unittest.mock import MagicMock
from modules.workers.memory_worker.worker import MemoryWorker

class TestMemoryWorker(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.worker = MemoryWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()

    def test_execute_memory_success(self):
        msg_mock = MagicMock()
        msg_mock.content = "Recalled fact: User prefers dark theme and Python programming."
        self.worker._agent.invoke.return_value = {"messages": [msg_mock]}

        res = self.worker.execute_task("task_mem_1", "Recall user preferences", {})
        self.assertEqual(res["status"], "completed")
        self.assertIn("dark theme", res["summary"])

    def test_execute_memory_failure(self):
        self.worker._agent.invoke.side_effect = Exception("Memory storage connection error")
        res = self.worker.execute_task("task_mem_1", "Recall user preferences", {})
        self.assertEqual(res["status"], "failed")
        self.assertIn("connection error", res["error_message"])

if __name__ == "__main__":
    unittest.main()
