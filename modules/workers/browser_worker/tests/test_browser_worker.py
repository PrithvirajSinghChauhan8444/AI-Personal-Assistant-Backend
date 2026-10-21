import unittest
from unittest.mock import MagicMock, patch
from modules.workers.browser_worker.worker import BrowserWorker
from modules.workers.browser_worker.tools import (
    browser_navigate,
    browser_click,
    browser_input,
    browser_scroll,
    browser_read_content,
    browser_screenshot
)

class TestBrowserWorker(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.worker = BrowserWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()

    def test_execute_browser_success(self):
        msg_mock = MagicMock()
        msg_mock.content = "Navigated to page and extracted headlines."
        self.worker._agent.invoke.return_value = {"messages": [msg_mock]}

        res = self.worker.execute_task("task_br_1", "Read news headlines", {})
        self.assertEqual(res["status"], "completed")
        self.assertIn("headlines", res["summary"])

    def test_execute_browser_failure(self):
        self.worker._agent.invoke.side_effect = Exception("Page navigation timeout")
        res = self.worker.execute_task("task_br_1", "Read news headlines", {})
        self.assertEqual(res["status"], "failed")
        self.assertIn("Page navigation timeout", res["error_message"])

    @patch("modules.workers.browser_worker.integrations.browser_client.navigate_to_url")
    def test_browser_navigate_tool(self, mock_nav):
        mock_nav.return_value = "Navigated to https://example.com"
        res = browser_navigate.invoke({"url": "https://example.com"})
        self.assertIn("example.com", res)

    @patch("modules.workers.browser_worker.integrations.browser_client.click_element")
    def test_browser_click_tool(self, mock_click):
        mock_click.return_value = "Clicked element 1"
        res = browser_click.invoke({"element_index": 1})
        self.assertIn("Clicked element 1", res)

    @patch("modules.workers.browser_worker.integrations.browser_client.type_text")
    def test_browser_input_tool(self, mock_type):
        mock_type.return_value = "Typed 'hello' into element 2"
        res = browser_input.invoke({"element_index": 2, "text": "hello", "press_enter": True})
        self.assertIn("Typed 'hello'", res)

if __name__ == "__main__":
    unittest.main()
