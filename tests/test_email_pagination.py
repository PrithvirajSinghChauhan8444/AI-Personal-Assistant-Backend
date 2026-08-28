import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import json

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.Integrations.Gmail.gmail_reader import read_gmail_email
from src.CoreFunctions.Integrations.Gmail.email_cache import get_cached_email, clear_email_cache, cache_email
from src.CoreFunctions.Integrations.Gmail.email_cleaner import clean_body_content

class TestEmailPagination(unittest.TestCase):
    def setUp(self):
        # Clear the cache before each test
        clear_email_cache("msg_test_pagination")
        
    def tearDown(self):
        clear_email_cache("msg_test_pagination")

    def test_clean_body_content_no_truncation(self):
        # Test clean_body_content has a working truncate=False param
        long_text = "a" * 3000
        cleaned = clean_body_content(long_text, truncate=False)
        self.assertEqual(len(cleaned), 3000)
        self.assertNotIn("... [truncated]", cleaned)

        # Test default clean_body_content still truncates
        cleaned_default = clean_body_content(long_text)
        self.assertEqual(len(cleaned_default), 2000 + len("\n... [truncated]"))

    @patch('src.CoreFunctions.Integrations.Gmail.gmail_reader.get_gmail_service')
    def test_read_email_pagination_and_caching(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Build 5000 char long body (plain-text)
        long_body = "".join([str(i % 10) for i in range(5000)])
        
        # Mock payload data
        mock_msg_payload = {
            "id": "msg_test_pagination",
            "threadId": "thread_test_123",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "Subject", "value": "Pagination Test Subject"},
                    {"name": "From", "value": "test@example.com"},
                    {"name": "Date", "value": "Thu, 27 Aug 2026 12:00:00 -0400"},
                    {"name": "To", "value": "me@example.com"}
                ],
                "body": {
                    # No data at root, it's text/plain directly
                    "data": ""
                }
            }
        }
        
        # Since it is a text/plain type, we mock the extract_body helper target:
        # In gmail_reader.py, if 'parts' not in payload, it reads body/data or parts recursively.
        # Let's mock payload parts list to return text/plain body.
        import base64
        body_b64 = base64.urlsafe_b64encode(long_body.encode('utf-8')).decode('utf-8')
        mock_msg_payload["payload"]["body"]["data"] = body_b64
        
        # Configure messages().get().execute() to return mock payload
        mock_service.users().messages().get().execute.return_value = mock_msg_payload
        
        # Reset mock call counts after setup configuration
        mock_service.users().messages().get.reset_mock()
        
        # --- Page 1 Reading (Should hit Gmail API and store in cache) ---
        res_page_1 = read_gmail_email("msg_test_pagination", account="personal", page=1, page_size=2000)
        
        # Verify call count
        self.assertEqual(mock_service.users().messages().get.call_count, 1)
        
        # Verify page 1 structure
        self.assertEqual(res_page_1["id"], "msg_test_pagination")
        self.assertEqual(res_page_1["subject"], "<email_subject>Pagination Test Subject</email_subject>")
        self.assertEqual(res_page_1["body"], f"<email_body>{long_body[0:2000]}</email_body>")
        
        pagination_1 = res_page_1["pagination"]
        self.assertEqual(pagination_1["current_page"], 1)
        self.assertEqual(pagination_1["total_pages"], 3)
        self.assertTrue(pagination_1["has_more"])
        self.assertEqual(pagination_1["total_characters"], 5000)
        
        # Verify it was stored in local SQLite cache
        cached_info = get_cached_email("msg_test_pagination", "personal")
        self.assertIsNotNone(cached_info)
        self.assertEqual(cached_info["body"], long_body)
        
        # Reset mock to verify we don't hit the API on Page 2
        mock_service.users().messages().get.reset_mock()
        
        # --- Page 2 Reading (Should hit cache directly) ---
        res_page_2 = read_gmail_email("msg_test_pagination", account="personal", page=2, page_size=2000)
        
        # Verify Gmail API was NOT called
        mock_service.users().messages().get.assert_not_called()
        
        # Verify page 2 structure
        self.assertEqual(res_page_2["body"], f"<email_body>{long_body[2000:4000]}</email_body>")
        pagination_2 = res_page_2["pagination"]
        self.assertEqual(pagination_2["current_page"], 2)
        self.assertTrue(pagination_2["has_more"])
        
        # --- Page 3 Reading (Last Page) ---
        res_page_3 = read_gmail_email("msg_test_pagination", account="personal", page=3, page_size=2000)
        
        self.assertEqual(res_page_3["body"], f"<email_body>{long_body[4000:5000]}</email_body>")
        pagination_3 = res_page_3["pagination"]
        self.assertEqual(pagination_3["current_page"], 3)
        self.assertFalse(pagination_3["has_more"])

if __name__ == "__main__":
    unittest.main()
