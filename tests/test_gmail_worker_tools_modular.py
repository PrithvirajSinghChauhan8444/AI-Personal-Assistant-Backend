import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import json

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from tests.mocks.mock_gmail_service import create_mock_gmail_service
from src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_prompt import compile_tool_prompt_section
from src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_worker_tools import gmail_tools

class TestGmailWorkerToolsModular(unittest.TestCase):
    def setUp(self):
        self.mock_service = create_mock_gmail_service()
        
    def test_prompt_compilation(self):
        prompt_section = compile_tool_prompt_section(gmail_tools)
        # Assert compiled prompt contains key tool definitions
        self.assertIn("count_emails", prompt_section)
        self.assertIn("fetch_email_ids", prompt_section)
        self.assertIn("read_email_content", prompt_section)
        self.assertIn("process_email", prompt_section)
        self.assertIn("send_email", prompt_section)
        self.assertIn("delete_emails_permanently", prompt_section)

    @patch('src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_worker_tools.gmail_worker_tool_count_emails.get_gmail_service')
    def test_tool_count_emails(self, mock_get_service):
        mock_get_service.return_value = self.mock_service
        self.mock_service.set_list_response([{"id": "msg1"}, {"id": "msg2"}])
        
        from src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_worker_tools.gmail_worker_tool_count_emails import count_emails
        res_str = count_emails("is:unread", "personal")
        res = json.loads(res_str)
        self.assertEqual(res["total_matching_emails"], 2)
        
    @patch('src.CoreFunctions.Integrations.Gmail.gmail_reader.get_gmail_service')
    def test_tool_fetch_email_ids(self, mock_get_service):
        mock_get_service.return_value = self.mock_service
        self.mock_service.set_list_response([{"id": "msg1"}, {"id": "msg2"}])
        
        from src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_worker_tools.gmail_worker_tool_fetch_email_ids import fetch_email_ids_tool
        res_str = fetch_email_ids_tool("is:unread", "personal")
        res = json.loads(res_str)
        self.assertIn("job_id", res)
        self.assertEqual(res["total_matching_emails"], 2)

    @patch('src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_worker_tools.gmail_worker_tool_delete_emails_permanently.get_gmail_service')
    def test_tool_delete_emails_permanently_confirmed(self, mock_get_service):
        mock_get_service.return_value = self.mock_service
        
        from src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_worker_tools.gmail_worker_tool_delete_emails_permanently import delete_emails_permanently
        # Call unconfirmed
        unconfirmed_res = delete_emails_permanently(message_ids=["msg1"], confirmed=False)
        self.assertIn("❌ Error", unconfirmed_res)
        self.mock_service._messages_delete_mock.execute.assert_not_called()
        
        # Call confirmed
        confirmed_res = delete_emails_permanently(message_ids=["msg1"], confirmed=True)
        res = json.loads(confirmed_res)
        self.assertEqual(res["status"], "success")
        self.assertEqual(self.mock_service._messages_delete_mock.execute.call_count, 1)

if __name__ == "__main__":
    unittest.main()
