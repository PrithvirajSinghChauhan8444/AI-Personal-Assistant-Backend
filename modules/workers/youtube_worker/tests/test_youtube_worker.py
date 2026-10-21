import unittest
from unittest.mock import MagicMock
from modules.workers.youtube_worker.worker import YoutubeWorker

class TestYoutubeWorker(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.worker = YoutubeWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()

    def test_execute_youtube_success(self):
        msg_mock = MagicMock()
        msg_mock.content = "Found 2 videos: [FastAPI 101](<url>https://youtube.com/watch?v=123</url>)."
        self.worker._agent.invoke.return_value = {"messages": [msg_mock]}

        res = self.worker.execute_task("task_yt_1", "Search for FastAPI videos", {})
        self.assertEqual(res["status"], "completed")
        self.assertIn("FastAPI 101", res["summary"])

    def test_execute_youtube_failure(self):
        self.worker._agent.invoke.side_effect = Exception("YouTube Data API quota exceeded")
        res = self.worker.execute_task("task_yt_1", "Search for FastAPI videos", {})
        self.assertEqual(res["status"], "failed")
        self.assertIn("quota exceeded", res["error_message"])

if __name__ == "__main__":
    unittest.main()
