import os
import sys
import unittest
import tempfile
import shutil
import json
from datetime import datetime

# Set path to root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, migrate_json_to_sqlite, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import delete_vector_fact, store_vector, search_vector

class TestDatabaseMemory(unittest.TestCase):
    def setUp(self):
        # We will use a temporary database file for isolation
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_cache.db")
        
        # Override the database path dynamically
        self.original_db_path = UnifiedMemory().db_path
        UnifiedMemory._instance = None # Reset singleton
        self.um = UnifiedMemory(db_path=self.db_path)

    def tearDown(self):
        # Reset singleton to original settings and clean up directory
        UnifiedMemory._instance = None
        shutil.rmtree(self.test_dir)

    def test_store_and_fetch_memory(self):
        # Test basic store and fetch for different categories
        store_memory("user", "favorite_city", "Paris")
        store_memory("past", "last_email_count", "10")
        
        # Smart lookup
        val_city = fetch_memory(None, "favorite_city")
        val_count = fetch_memory(None, "last_email_count")
        
        self.assertEqual(val_city, "Paris")
        self.assertEqual(val_count, "10")
        
        # Direct category lookup
        self.assertEqual(fetch_memory("user", "favorite_city"), "Paris")
        self.assertIsNone(fetch_memory("user", "last_email_count")) # Wrong category

    def test_duplicate_checking(self):
        # Test that duplicate values are not stored
        store_memory("user", "favorite_city", "Berlin")
        result = store_memory("user", "favorite_city", "Berlin")
        
        self.assertIn("already exists", result)

    def test_full_category_dump(self):
        # Store several keys
        store_memory("user", "name", "John")
        store_memory("user", "hobby", "Coding")
        
        dump = fetch_memory("user")
        self.assertIn("name", dump)
        self.assertIn("hobby", dump)
        self.assertEqual(dump["name"]["value"], "John")
        self.assertEqual(dump["hobby"]["value"], "Coding")

    def test_json_to_sqlite_migration(self):
        # Create a mock legacy JSON file
        legacy_path = os.path.join(self.test_dir, "user_info.json")
        legacy_data = {
            "name": {
                "value": "Alice",
                "timestamp": "2026-06-18T12:00:00"
            },
            "age": "25"
        }
        with open(legacy_path, "w") as f:
            json.dump(legacy_data, f)
            
        # Temporarily mock the FILES dict in memory.py to point to our legacy JSON path
        from src.CoreFunctions.Infrastructure import memory
        original_files = memory.FILES
        memory.FILES = {
            "user": legacy_path,
            "current": os.path.join(self.test_dir, "current_chat.json"),
            "past": os.path.join(self.test_dir, "past_memory.json"),
        }
        
        try:
            # Run migration
            migrate_json_to_sqlite()
            
            # Verify data is loaded into SQLite database
            self.assertEqual(fetch_memory("user", "name"), "Alice")
            self.assertEqual(fetch_memory("user", "age"), "25")
            
            # Verify the legacy JSON file was backed up and renamed
            self.assertFalse(os.path.exists(legacy_path))
            self.assertTrue(os.path.exists(legacy_path + ".bak"))
            
        finally:
            memory.FILES = original_files

    def test_delete_memory(self):
        # Store a value
        store_memory("user", "mail", "test@test.com")
        self.assertEqual(fetch_memory("user", "mail"), "test@test.com")
        
        # Delete the value
        delete_memory("user", "mail")
        self.assertIsNone(fetch_memory("user", "mail"))

    def test_delete_vector_fact(self):
        # Store a fact
        fact = "This is a temporary test vector fact."
        store_vector(fact)
        self.assertIn(fact, search_vector("temporary test vector", k=1))
        
        # Delete the fact
        success = delete_vector_fact(fact)
        self.assertTrue(success)
        
        # Re-search
        results = search_vector("temporary test vector", k=1)
        self.assertNotIn(fact, results)

if __name__ == '__main__':
    unittest.main()
