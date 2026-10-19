import unittest
import os
import tempfile
import json
from modules.infrastructure.storage.unified_storage import UnifiedStorage
from modules.infrastructure.observability.logger import ModuleLogger
from modules.infrastructure.security.vault import get_console_lock

class TestInfrastructure(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_cache.db")
        self.storage = UnifiedStorage(self.db_path)
        self.logger = ModuleLogger(self.temp_dir.name)

    def tearDown(self):
        self.storage.close()
        self.temp_dir.cleanup()

    def test_storage_crud(self):
        self.storage.set("test_key", {"data": 123})
        val = self.storage.get("test_key")
        self.assertEqual(val, {"data": 123})

        keys = self.storage.list_keys("test_")
        self.assertIn("test_key", keys)

        self.storage.delete("test_key")
        self.assertIsNone(self.storage.get("test_key"))

    def test_logger_event(self):
        self.logger.log_event("TestModule", "test_event", {"status": "ok"})
        log_file = os.path.join(self.temp_dir.name, "modular_execution.jsonl")
        self.assertTrue(os.path.exists(log_file))
        with open(log_file, "r") as f:
            line = f.readline()
            data = json.loads(line)
            self.assertEqual(data["module"], "TestModule")
            self.assertEqual(data["event"], "test_event")

    def test_console_lock_instance(self):
        lock = get_console_lock()
        self.assertIsNotNone(lock)

if __name__ == "__main__":
    unittest.main()
