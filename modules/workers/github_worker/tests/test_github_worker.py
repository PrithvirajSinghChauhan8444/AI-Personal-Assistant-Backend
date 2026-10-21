import unittest
from unittest.mock import MagicMock
from modules.workers.github_worker.worker import GithubWorker

class TestGithubWorker(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.worker = GithubWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()

    def test_execute_github_success(self):
        msg_mock = MagicMock()
        msg_mock.content = "Found 3 repositories: repo1, repo2, repo3."
        self.worker._agent.invoke.return_value = {"messages": [msg_mock]}

        res = self.worker.execute_task("task_gh_1", "List my repos", {})
        self.assertEqual(res["status"], "completed")
        self.assertIn("repo1", res["summary"])

    def test_execute_github_failure(self):
        self.worker._agent.invoke.side_effect = Exception("GitHub API rate limit exceeded")
        res = self.worker.execute_task("task_gh_1", "List my repos", {})
        self.assertEqual(res["status"], "failed")
        self.assertIn("rate limit exceeded", res["error_message"])

if __name__ == "__main__":
    unittest.main()
