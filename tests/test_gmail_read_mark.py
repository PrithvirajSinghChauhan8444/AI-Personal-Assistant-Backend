import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import json

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.Integrations.Gmail.gmail_ops import read_gmail_msg, fetch_unread_mails

class TestGmailReadMark(unittest.TestCase):
    @patch('src.CoreFunctions.Integrations.Gmail.gmail_ops.read_gmail_email')
    @patch('src.CoreFunctions.Integrations.Gmail.gmail_ops.mark_gmail_as_read')
    def test_read_gmail_msg_default(self, mock_mark, mock_read):
        # Configure mocks
        mock_read.return_value = {"id": "123", "subject": "Test", "body": "Hello"}
        
        # Call read_gmail_msg with default mark_read=False
        res_str = read_gmail_msg("123")
        res = json.loads(res_str)
        
        # Verify mark_gmail_as_read was not called
        mock_mark.assert_not_called()
        mock_read.assert_called_once_with("123", account="personal")
        self.assertEqual(res["id"], "123")
        self.assertNotIn("mark_read_status", res)

    @patch('src.CoreFunctions.Integrations.Gmail.gmail_ops.read_gmail_email')
    @patch('src.CoreFunctions.Integrations.Gmail.gmail_ops.mark_gmail_as_read')
    def test_read_gmail_msg_mark_true(self, mock_mark, mock_read):
        # Configure mocks
        mock_read.return_value = {"id": "123", "subject": "Test", "body": "Hello"}
        mock_mark.return_value = "Successfully marked email 123 as read on account 'personal'."
        
        # Call read_gmail_msg with mark_read=True
        res_str = read_gmail_msg("123", mark_read=True)
        res = json.loads(res_str)
        
        # Verify mark_gmail_as_read was called
        mock_mark.assert_called_once_with("123", account="personal")
        mock_read.assert_called_once_with("123", account="personal")
        self.assertEqual(res["id"], "123")
        self.assertEqual(res["mark_read_status"], "Successfully marked email 123 as read on account 'personal'.")

    @patch('src.CoreFunctions.Integrations.Gmail.gmail_ops.search_gmail_emails')
    def test_fetch_unread_mails_both(self, mock_search):
        # Configure mock search_gmail_emails
        def mock_search_side_effect(query, limit, page_token, account):
            if account == "personal":
                return {"count": 1, "emails": [{"id": "p1", "subject": "Job Offer"}]}
            elif account == "college":
                return {"count": 1, "emails": [{"id": "c1", "subject": "Internship details"}]}
            return {"count": 0, "emails": []}
            
        mock_search.side_effect = mock_search_side_effect
        
        # Call fetch_unread_mails with account="both"
        res_str = fetch_unread_mails(mode="list", limit=5, account="both")
        res = json.loads(res_str)
        
        # Verify both personal and college searches were made
        self.assertIn("personal", res)
        self.assertIn("college", res)
        self.assertEqual(res["personal"]["emails"][0]["id"], "p1")
        self.assertEqual(res["college"]["emails"][0]["id"], "c1")
        self.assertEqual(mock_search.call_count, 2)

    @patch('src.CoreFunctions.Integrations.Gmail.gmail_ops.get_unread_count')
    def test_fetch_unread_mails_count(self, mock_count):
        # Configure mock get_unread_count
        def mock_count_side_effect(account):
            if account == "personal":
                return {"unread_messages": 10, "unread_threads": 5}
            elif account == "college":
                return {"unread_messages": 20, "unread_threads": 8}
            return {"unread_messages": 0, "unread_threads": 0}
            
        mock_count.side_effect = mock_count_side_effect
        
        # Call fetch_unread_mails in count mode for both accounts
        res_str = fetch_unread_mails(mode="count", account="both")
        res = json.loads(res_str)
        
        self.assertEqual(res["personal"]["unread_messages"], 10)
        self.assertEqual(res["college"]["unread_messages"], 20)
        self.assertEqual(mock_count.call_count, 2)

    @patch('src.CoreFunctions.Integrations.Gmail.gmail_ops.search_gmail_emails')
    def test_fetch_unread_mails_limit_capping(self, mock_search):
        mock_search.return_value = {"count": 0, "emails": []}
        
        # Call with limit exceeding cap (e.g., 15)
        fetch_unread_mails(mode="list", limit=15, account="personal")
        
        # Verify the actual call was capped at 10
        mock_search.assert_called_once_with("is:unread", 10, page_token=None, account="personal")

if __name__ == "__main__":
    unittest.main()
