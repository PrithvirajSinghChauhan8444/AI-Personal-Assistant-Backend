import unittest
from unittest.mock import MagicMock
from modules.workers.productivity_worker.worker import ProductivityWorker

class TestProductivityWorker(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.worker = ProductivityWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()

    def test_execute_calendar_success(self):
        msg_mock = MagicMock()
        msg_mock.content = "Meeting scheduled at 2:00 PM."
        self.worker._agent.invoke.return_value = {"messages": [msg_mock]}

        res = self.worker.execute_task("task_cal_1", "Schedule meeting", {})
        self.assertEqual(res["status"], "completed")
        self.assertIn("2:00 PM", res["summary"])

    def test_execute_calendar_failure(self):
        self.worker._agent.invoke.side_effect = Exception("Calendar API unreachable")
        res = self.worker.execute_task("task_cal_1", "Schedule meeting", {})
        self.assertEqual(res["status"], "failed")
        self.assertIn("Calendar API unreachable", res["error_message"])

if __name__ == "__main__":
    unittest.main()
