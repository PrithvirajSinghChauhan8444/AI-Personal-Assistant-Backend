import unittest
from unittest.mock import MagicMock
from modules.workers.classroom_worker.worker import ClassroomWorker

class TestClassroomWorker(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.worker = ClassroomWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()

    def test_execute_classroom_success(self):
        msg_mock = MagicMock()
        msg_mock.content = "Found 2 active courses: CS101 and MATH202."
        self.worker._agent.invoke.return_value = {"messages": [msg_mock]}

        res = self.worker.execute_task("task_cr_1", "Fetch my courses", {})
        self.assertEqual(res["status"], "completed")
        self.assertIn("CS101", res["summary"])

    def test_execute_classroom_failure(self):
        self.worker._agent.invoke.side_effect = Exception("Google Classroom API authentication error")
        res = self.worker.execute_task("task_cr_1", "Fetch my courses", {})
        self.assertEqual(res["status"], "failed")
        self.assertIn("authentication error", res["error_message"])

if __name__ == "__main__":
    unittest.main()
