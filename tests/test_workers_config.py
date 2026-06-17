import os
import sys
import json
import unittest
from unittest.mock import patch

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.StateGraph.registry import WorkerRegistry, scan_and_register_workers
from src.CoreFunctions.StateGraph.executor import get_model_for_worker

class TestWorkersConfig(unittest.TestCase):
    def setUp(self):
        # Scan and register to ensure we start clean and loaded
        scan_and_register_workers()
        # Backup the current config if exists
        self.config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
        self.config_path = os.path.join(self.config_dir, "workers_config.json")
        self.backup_path = self.config_path + ".bak"
        if os.path.exists(self.config_path):
            os.replace(self.config_path, self.backup_path)

    def tearDown(self):
        # Restore backup config
        if os.path.exists(self.backup_path):
            os.replace(self.backup_path, self.config_path)
        elif os.path.exists(self.config_path):
            os.remove(self.config_path)
            
        # Reset WorkerRegistry configuration
        WorkerRegistry._config = {}

    def test_active_inactive_filtering(self):
        # Create a test config where GmailWorker is inactive
        test_config = {
            "SystemWorker": {
                "model": "gemini-3.1-flash-lite",
                "active": True
            },
            "GmailWorker": {
                "model": "gemini-3.1-flash-lite",
                "active": False
            }
        }
        
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(test_config, f, indent=4)
            
        # Force reload config
        WorkerRegistry.load_and_sync_config()
        
        # Verify GmailWorker is not in active workers
        active_workers = WorkerRegistry.get_all_workers()
        self.assertNotIn("GmailWorker", active_workers)
        self.assertIn("SystemWorker", active_workers)
        
        # Verify get_worker_names does not contain GmailWorker
        names = WorkerRegistry.get_worker_names()
        self.assertNotIn("GmailWorker", names)
        self.assertIn("SystemWorker", names)
        
        # Verify get_worker raises KeyError for GmailWorker
        with self.assertRaises(KeyError):
            WorkerRegistry.get_worker("GmailWorker")

    def test_dynamic_model_configuration(self):
        # Create a test config where SystemWorker model is customized
        custom_model = "custom-test-model"
        test_config = {
            "SystemWorker": {
                "model": custom_model,
                "active": True
            }
        }
        
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(test_config, f, indent=4)
            
        # Force reload config
        WorkerRegistry.load_and_sync_config()
        
        # Retrieve the cached model (we mock the LLM initializers to avoid external API calls)
        with patch('src.CoreFunctions.StateGraph.executor.ChatGoogleGenerativeAI') as mock_gemini, \
             patch('src.CoreFunctions.StateGraph.executor.ChatOllama') as mock_ollama:
             
            # Test getting OLLAMA model (non-gemini contains no gemini string)
            get_model_for_worker("SystemWorker")
            mock_ollama.assert_called_once_with(
                model=custom_model,
                temperature=0,
                options={"thinking": True}
            )

if __name__ == "__main__":
    unittest.main()
