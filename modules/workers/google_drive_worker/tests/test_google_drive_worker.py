import unittest
from unittest.mock import MagicMock
from modules.workers.google_drive_worker.worker import GoogleDriveWorker

class TestGoogleDriveWorker(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.worker = GoogleDriveWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()

    def test_execute_drive_success(self):
        msg_mock = MagicMock()
        msg_mock.content = "Found 2 files: project_doc.pdf, budget.xlsx."
        self.worker._agent.invoke.return_value = {"messages": [msg_mock]}

        res = self.worker.execute_task("task_gdrive_1", "List my Drive files", {})
        self.assertEqual(res["status"], "completed")
        self.assertIn("project_doc.pdf", res["summary"])

    def test_execute_drive_failure(self):
        self.worker._agent.invoke.side_effect = Exception("Google Drive API rate limit")
        res = self.worker.execute_task("task_gdrive_1", "List my Drive files", {})
        self.assertEqual(res["status"], "failed")
        self.assertIn("rate limit", res["error_message"])

if __name__ == "__main__":
    unittest.main()
