import unittest
from unittest.mock import MagicMock
from modules.workers.communication_worker.worker import CommunicationWorker

class TestCommunicationWorker(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.worker = CommunicationWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()

    def test_execute_email_query_success(self):
        msg_mock = MagicMock()
        msg_mock.content = "Found 2 unread emails."
        self.worker._agent.invoke.return_value = {"messages": [msg_mock]}

        res = self.worker.execute_task("task_email_1", "Check unread emails", {})
        self.assertEqual(res["status"], "completed")
        self.assertIn("unread", res["summary"])

    def test_execute_email_failure_handling(self):
        self.worker._agent.invoke.side_effect = Exception("OAuth token expired")
        res = self.worker.execute_task("task_email_1", "Send email", {})
        self.assertEqual(res["status"], "failed")
        self.assertIn("OAuth token expired", res["error_message"])

if __name__ == "__main__":
    unittest.main()
