import os
import sys
import unittest
import tempfile
import shutil
import threading
import time

# Set path to root and src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Prevent duplicate module objects being loaded under different namespaces
import src.CoreFunctions.unified_memory
sys.modules['CoreFunctions.unified_memory'] = src.CoreFunctions.unified_memory

import src.CoreFunctions.memory
sys.modules['CoreFunctions.memory'] = src.CoreFunctions.memory

import src.CoreFunctions.StateGraph.registry
sys.modules['CoreFunctions.StateGraph.registry'] = src.CoreFunctions.StateGraph.registry

from src.CoreFunctions.unified_memory import UnifiedMemory
from src.CoreFunctions.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.StateGraph.registry import WorkerRegistry, BaseWorker

class MockTestWorker(BaseWorker):
    def __init__(self, name_val, enable_mem):
        self._name = name_val
        self._enable_mem = enable_mem

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Mock worker description"

    @property
    def instructions(self) -> str:
        return "Mock instructions"

    @property
    def tools(self) -> list:
        return []

    @property
    def categories(self) -> list:
        return []

    @property
    def enable_worker_memory(self) -> bool:
        return self._enable_mem


class TestWorkerMemory(unittest.TestCase):
    def setUp(self):
        # Setup temporary database for isolation
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_worker_cache.db")
        
        # Override the database path dynamically
        self.original_db_path = UnifiedMemory().db_path
        UnifiedMemory._instance = None # Reset singleton
        self.um = UnifiedMemory(db_path=self.db_path)

        # Backup WorkerRegistry state
        self.original_registry = dict(WorkerRegistry._registry)
        self.original_config = dict(WorkerRegistry._config)

        # Clear and register mock workers
        WorkerRegistry._registry = {}
        WorkerRegistry._config = {}
        
        self.worker1 = MockTestWorker("GmailWorker", enable_mem=True)
        self.worker2 = MockTestWorker("ObsidianWorker", enable_mem=False)
        
        WorkerRegistry._registry["GmailWorker"] = self.worker1
        WorkerRegistry._registry["ObsidianWorker"] = self.worker2
        
        # Sync config dictionary
        WorkerRegistry._config["GmailWorker"] = {
            "model": "gemini-3.1-flash-lite",
            "active": True,
            "enable_worker_memory": True
        }
        WorkerRegistry._config["ObsidianWorker"] = {
            "model": "gemma4:e4b",
            "active": True,
            "enable_worker_memory": False
        }
        
        # Clean up any existing worker keys to avoid dirty state from prior runs/tests
        try:
            for k in self.um.list_keys("worker:*"):
                self.um.delete_memory(k)
        except Exception:
            pass

    def tearDown(self):
        # Clean up worker keys
        try:
            for k in self.um.list_keys("worker:*"):
                self.um.delete_memory(k)
        except Exception:
            pass

        # Reset registry and config to original
        WorkerRegistry._registry = self.original_registry
        WorkerRegistry._config = self.original_config
        
        # Reset singleton to original settings and clean up directory
        UnifiedMemory._instance = None
        shutil.rmtree(self.test_dir)

    def test_context_set_and_get(self):
        # Test basic UnifiedMemory context tracker
        self.assertIsNone(UnifiedMemory.get_current_worker())
        
        token = UnifiedMemory.set_current_worker("GmailWorker")
        self.assertEqual(UnifiedMemory.get_current_worker(), "GmailWorker")
        
        UnifiedMemory.reset_current_worker(token)
        self.assertIsNone(UnifiedMemory.get_current_worker())

    def test_store_and_fetch_worker_memory_explicit(self):
        # Explicit worker category storage and fetching
        store_memory("worker:GmailWorker", "signature", "Best regards, John")
        
        # Verify direct category lookup
        val = fetch_memory("worker:GmailWorker", "signature")
        self.assertEqual(val, "Best regards, John")
        
        # Verify smart recall does not check if context is not active
        self.assertIsNone(fetch_memory(category=None, key="signature"))

    def test_waterfall_lookup_enabled(self):
        # Store a value specifically for GmailWorker
        store_memory("worker:GmailWorker", "signature", "Best regards, John")
        
        # Activate worker context
        token = UnifiedMemory.set_current_worker("GmailWorker")
        try:
            # Smart recall should fall back to worker memory
            val = fetch_memory(category=None, key="signature")
            self.assertEqual(val, "Best regards, John")
            
            # Now set a user-level override
            store_memory("user", "signature", "Cheers, John")
            
            # Smart recall should now prioritize user-level memory
            val = fetch_memory(category=None, key="signature")
            self.assertEqual(val, "Cheers, John")
            
            # Delete user override and it should fall back to worker memory again
            delete_memory("user", "signature")
            val = fetch_memory(category=None, key="signature")
            self.assertEqual(val, "Best regards, John")
        finally:
            UnifiedMemory.reset_current_worker(token)

    def test_waterfall_lookup_disabled(self):
        # Store a value specifically for ObsidianWorker
        store_memory("worker:ObsidianWorker", "vault_path", "/documents/notes")
        
        # Activate worker context for ObsidianWorker (memory fallback is disabled)
        token = UnifiedMemory.set_current_worker("ObsidianWorker")
        try:
            # Smart recall should NOT fall back to worker memory because it's disabled
            val = fetch_memory(category=None, key="vault_path")
            self.assertIsNone(val)
            
            # But direct lookup still works
            val_direct = fetch_memory("worker:ObsidianWorker", "vault_path")
            self.assertEqual(val_direct, "/documents/notes")
        finally:
            UnifiedMemory.reset_current_worker(token)

    def test_full_category_dump_worker(self):
        store_memory("worker:GmailWorker", "sig", "Best")
        store_memory("worker:GmailWorker", "draft_count", "5")
        
        dump = fetch_memory("worker:GmailWorker")
        self.assertEqual(len(dump), 2)
        self.assertEqual(dump["sig"]["value"], "Best")
        self.assertEqual(dump["draft_count"]["value"], "5")

    def test_delete_worker_memory(self):
        store_memory("worker:GmailWorker", "key_to_del", "val")
        self.assertEqual(fetch_memory("worker:GmailWorker", "key_to_del"), "val")
        
        delete_memory("worker:GmailWorker", "key_to_del")
        self.assertIsNone(fetch_memory("worker:GmailWorker", "key_to_del"))

    def test_multithreaded_context_isolation(self):
        # Test concurrent worker threads to ensure context isolation holds
        store_memory("worker:GmailWorker", "shared_key", "GmailData")
        store_memory("worker:ObsidianWorker", "shared_key", "ObsidianData")
        
        results = {}
        
        def run_thread(worker_name):
            token = UnifiedMemory.set_current_worker(worker_name)
            try:
                # Simulate some random work/delay
                time.sleep(0.05)
                # Query direct and smart recall
                val = fetch_memory(category="worker", key="shared_key")
                results[worker_name] = val
            finally:
                UnifiedMemory.reset_current_worker(token)

        t1 = threading.Thread(target=run_thread, args=("GmailWorker",))
        t2 = threading.Thread(target=run_thread, args=("ObsidianWorker",))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        self.assertEqual(results.get("GmailWorker"), "GmailData")
        self.assertEqual(results.get("ObsidianWorker"), "ObsidianData")

if __name__ == '__main__':
    unittest.main()
