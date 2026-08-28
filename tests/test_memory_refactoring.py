import os
import sys
import unittest
import tempfile
import shutil
import json
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory, SQLiteMemoryEngine
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory, route_fact
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector, consolidate_facts

class TestMemoryRefactoring(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_cache.db")
        UnifiedMemory._instance = None
        self.um = UnifiedMemory(db_path=self.db_path)

    def tearDown(self):
        UnifiedMemory._instance = None
        shutil.rmtree(self.test_dir)

    def test_sqlite_sharding_and_locks(self):
        store_memory("worker:GmailWorker", "last_sync_time", "2026-08-28T10:00:00")
        val = fetch_memory("worker:GmailWorker", "last_sync_time")
        self.assertEqual(val, "2026-08-28T10:00:00")
        
        shards_dir = os.path.join(self.test_dir, "shards")
        self.assertTrue(os.path.exists(shards_dir))
        shard_file = os.path.join(shards_dir, "worker_GmailWorker.db")
        self.assertTrue(os.path.exists(shard_file))

    def test_relations_graph(self):
        self.um.add_relation("Alice", "is married to", "Bob", "Married in 2020")
        self.um.add_relation("Alice", "works at", "Google", "Software Engineer")
        
        rel1 = self.um.query_relations(source="alice")
        self.assertEqual(len(rel1), 2)
        
        rel2 = self.um.query_relations(source="alice", relation="works at")
        self.assertEqual(len(rel2), 1)
        self.assertEqual(rel2[0]["target"], "google")
        self.assertEqual(rel2[0]["context"], "Software Engineer")
        
        self.um.delete_relation("Alice", "is married to", "Bob")
        rel3 = self.um.query_relations(source="alice")
        self.assertEqual(len(rel3), 1)
        self.assertEqual(rel3[0]["relation"], "works at")

    def test_memory_routing_gateway(self):
        msg = route_fact("fact1", "Charlie works at Microsoft", "past")
        self.assertIn("Relations Graph", msg)
        
        rels = self.um.query_relations(source="charlie")
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["relation"], "works at")
        self.assertEqual(rels[0]["target"], "microsoft")

        msg = route_fact("user_favorite_color", "blue", "user")
        self.assertIn("Structured KV", msg)
        self.assertEqual(fetch_memory("user", "user_favorite_color"), "blue")

    def test_vector_relevance_decay_and_cap(self):
        import src.CoreFunctions.Infrastructure.vector_memory as vm
        orig_index_path = vm.INDEX_PATH
        orig_data_path = vm.DATA_PATH
        orig_metadata_path = vm.METADATA_PATH
        orig_cold_path = vm.COLD_ARCHIVE_PATH
        
        vm.INDEX_PATH = os.path.join(self.test_dir, "test_index.faiss")
        vm.DATA_PATH = os.path.join(self.test_dir, "test_data.json")
        vm.METADATA_PATH = os.path.join(self.test_dir, "test_metadata.json")
        vm.COLD_ARCHIVE_PATH = os.path.join(self.test_dir, "test_cold_archive.json")
        
        try:
            for i in range(55):
                store_vector(f"This is test fact number {i}")
                
            data = vm._load_data()
            self.assertEqual(len(data), 50)
            
            self.assertTrue(os.path.exists(vm.COLD_ARCHIVE_PATH))
            with open(vm.COLD_ARCHIVE_PATH, "r") as f:
                cold_data = json.load(f)
            self.assertEqual(len(cold_data), 5)
            
        finally:
            vm.INDEX_PATH = orig_index_path
            vm.DATA_PATH = orig_data_path
            vm.METADATA_PATH = orig_metadata_path
            vm.COLD_ARCHIVE_PATH = orig_cold_path

if __name__ == '__main__':
    unittest.main()
