import os
import sys
import unittest
import tempfile
import shutil

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_tools import browser_tools
from src.CoreFunctions.unified_memory import UnifiedMemory
from src.CoreFunctions.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.tools import remember, recall

class TestBrowserCachingBehavior(unittest.TestCase):
    def setUp(self):
        # We will use a temporary database file for isolation
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_browser_cache.db")
        
        # Override the database path dynamically
        self.original_db_path = UnifiedMemory().db_path
        UnifiedMemory._instance = None # Reset singleton
        self.um = UnifiedMemory(db_path=self.db_path)

    def tearDown(self):
        # Reset singleton to original settings and clean up directory
        UnifiedMemory._instance = None
        shutil.rmtree(self.test_dir)

    def test_browser_tools_registration(self):
        """Verify remember and recall tools are registered for Browser workers."""
        tool_names = [t.name for t in browser_tools]
        self.assertIn("remember", tool_names)
        self.assertIn("recall", tool_names)

    def test_cache_key_validation_with_underscores(self):
        """Verify that cache keys using underscores are successfully validated and stored."""
        key = "url_example_com_more_info"
        val = "https://www.iana.org/domains/reserved"
        
        # This should succeed without raising ValueError since underscores conform to validation
        store_result = store_memory("past", key, val)
        self.assertIn("Stored", store_result)
        
        # Fetch the memory and confirm value matches
        retrieved_val = fetch_memory(None, key)
        self.assertEqual(retrieved_val, val)

    def test_cache_key_validation_failure_with_colons(self):
        """Verify that cache keys with colons or dots raise ValueError in the validation layer."""
        key_with_colon = "url:example.com:more_info"
        val = "https://www.iana.org/domains/reserved"
        
        with self.assertRaises(ValueError):
            store_memory("past", key_with_colon, val)

    def test_remember_and_recall_tools(self):
        """Verify the direct execution of the remember and recall tool functions."""
        key = "url_example_com_main"
        val = "https://example.com"
        
        # Test remember tool
        remember_res = remember(key, val, "past")
        self.assertIn("Saved memory", remember_res)
        
        # Test recall tool
        recall_res = recall(key)
        self.assertEqual(recall_res, val)

if __name__ == '__main__':
    unittest.main()
