import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.Integrations.Gmail.gmail_idle_daemon import GmailAccountIdleWorker
from src.CoreFunctions.Infrastructure.memory import fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory

class TestGmailIdleDaemonCaching(unittest.TestCase):
    def setUp(self):
        # Ensure cleanup of keys before test
        delete_memory("current", "last_received_email")
        delete_memory("current", "last_proactive_analysis")

    def tearDown(self):
        # Cleanup keys after test
        delete_memory("current", "last_received_email")
        delete_memory("current", "last_proactive_analysis")

    @patch('src.CoreFunctions.Integrations.Gmail.gmail_idle_daemon.fetch_unread_emails_detailed')
    @patch('src.CoreFunctions.StateGraph.main_graph.app.invoke')
    @patch('src.CoreFunctions.Integrations.Gmail.gmail_idle_daemon.play_beep')
    @patch('src.CoreFunctions.Integrations.Gmail.gmail_idle_daemon.trigger_desktop_notification')
    def test_trigger_agent_workflow_caches_metadata_and_analysis(
        self, mock_notify, mock_beep, mock_invoke, mock_fetch
    ):
        # Mock unread email
        mock_fetch.return_value = {
            "count": 1,
            "emails": [
                {
                    "id": "msg_xyz_123",
                    "sender": "sender@test.com",
                    "subject": "Test Caching Subject",
                    "body": "Test Caching Body content preview",
                    "date": "Fri, 21 Aug 2026 12:00:00 UT"
                }
            ]
        }
        
        # Mock LangGraph execution state
        mock_invoke.return_value = {
            "final_response": "Proactive analysis result: no action needed."
        }
        
        worker = GmailAccountIdleWorker("personal", "user@test.com")
        worker._trigger_agent_workflow()
        
        # Verify metadata is cached
        cached_meta = fetch_memory("current", "last_received_email")
        self.assertIsNotNone(cached_meta)
        self.assertIn("sender@test.com", cached_meta)
        self.assertIn("Test Caching Subject", cached_meta)
        self.assertIn("msg_xyz_123", cached_meta)
        
        # Verify analysis is cached
        cached_analysis = fetch_memory("current", "last_proactive_analysis")
        self.assertIsNotNone(cached_analysis)
        self.assertEqual(cached_analysis, "Proactive analysis result: no action needed.")

if __name__ == "__main__":
    unittest.main()
