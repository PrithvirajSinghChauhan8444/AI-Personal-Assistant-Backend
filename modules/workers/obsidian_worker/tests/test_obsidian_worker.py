import unittest
from unittest.mock import MagicMock
from modules.workers.obsidian_worker.worker import ObsidianWorker

class TestObsidianWorker(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.worker = ObsidianWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()

    def test_execute_obsidian_success(self):
        msg_mock = MagicMock()
        msg_mock.content = "Created note 'Daily Notes/2026-10-19.md' in vault."
        self.worker._agent.invoke.return_value = {"messages": [msg_mock]}

        res = self.worker.execute_task("task_obs_1", "Create daily note", {})
        self.assertEqual(res["status"], "completed")
        self.assertIn("Daily Notes", res["summary"])

    def test_execute_obsidian_failure(self):
        self.worker._agent.invoke.side_effect = Exception("Obsidian vault directory not found")
        res = self.worker.execute_task("task_obs_1", "Create daily note", {})
        self.assertEqual(res["status"], "failed")
        self.assertIn("vault directory not found", res["error_message"])

if __name__ == "__main__":
    unittest.main()
