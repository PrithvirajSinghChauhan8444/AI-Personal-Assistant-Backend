import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.Integrations.Gmail.gmail_db import get_cached_label_id, cache_label_id, get_job_info
from src.CoreFunctions.Integrations.Gmail.gmail_ops import clean_body_content, get_or_create_label, fetch_email_ids, read_gmail_email

class TestGmailNewSpec(unittest.TestCase):
    def test_html_cleaning_pipeline(self):
        html_input = """
        <html>
            <head>
                <style>body { background-color: red; }</style>
                <script>console.log("hello");</script>
            </head>
            <body>
                <h1>Hello Job Application</h1>
                <p>Please find details below:</p>
                <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIA..." width="100">
                <img src="https://tracking.com/pixel.gif" width="1" height="1">
                <p>This is some more text that should stay here.</p>
            </body>
        </html>
        """
        cleaned = clean_body_content(html_input)
        
        # Verify base64 blob stripped
        self.assertNotIn("iVBORw0KGgo", cleaned)
        # Verify style stripped
        self.assertNotIn("background-color", cleaned)
        # Verify script stripped
        self.assertNotIn("console.log", cleaned)
        # Verify tracking pixel stripped
        self.assertNotIn("pixel.gif", cleaned)
        # Verify clean plain text extracted
        self.assertIn("Hello Job Application", cleaned)
        self.assertIn("Please find details below:", cleaned)
        
    def test_html_truncation(self):
        long_input = "a" * 3000
        cleaned = clean_body_content(long_input)
        self.assertEqual(len(cleaned), 2000 + len("\n... [truncated]"))
        self.assertTrue(cleaned.endswith("\n... [truncated]"))

    @patch('src.CoreFunctions.Integrations.Gmail.gmail_labels.get_gmail_service')
    def test_label_caching(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Configure the list API to return some labels
        mock_service.users().labels().list().execute.return_value = {
            "labels": [{"name": "MyTestLabel", "id": "Label_123"}]
        }
        
        # Invalidate cache first
        from src.CoreFunctions.Integrations.Gmail.gmail_db import invalidate_label_cache
        invalidate_label_cache("personal", "MyTestLabel")
        
        # Reset mock call count after configuration
        mock_service.users().labels().list.reset_mock()
        
        # Call 1: should hit mock API and cache it
        label_id_1 = get_or_create_label(mock_service, "MyTestLabel", "personal")
        self.assertEqual(label_id_1, "Label_123")
        self.assertEqual(mock_service.users().labels().list.call_count, 1)
        
        # Verify it was cached in SQLite
        cached_id = get_cached_label_id("MyTestLabel", "personal")
        self.assertEqual(cached_id, "Label_123")
        
        # Reset mock to count fresh calls
        mock_service.users().labels().list.reset_mock()
        
        # Call 2: should retrieve from SQLite cache without calling API
        label_id_2 = get_or_create_label(mock_service, "MyTestLabel", "personal")
        self.assertEqual(label_id_2, "Label_123")
        mock_service.users().labels().list.assert_not_called()

    @patch('src.CoreFunctions.Integrations.Gmail.gmail_reader.get_gmail_service')
    def test_fetch_email_ids(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Configure list API return values
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "m1"}, {"id": "m2"}]
        }
        
        # Call fetch_email_ids
        job_info = fetch_email_ids("is:unread", account="personal")
        
        # Verify job schema
        self.assertIn("job_id", job_info)
        self.assertEqual(job_info["query"], "is:unread")
        self.assertEqual(job_info["total_matching_emails"], 2)
        self.assertIn("expires_at", job_info)
        
        # Verify job is stored in SQLite
        stored_ids, query, account, is_expired = get_job_info(job_info["job_id"])
        self.assertEqual(stored_ids, ["m1", "m2"])
        self.assertEqual(query, "is:unread")
        self.assertEqual(account, "personal")
        self.assertFalse(is_expired)

if __name__ == "__main__":
    unittest.main()
