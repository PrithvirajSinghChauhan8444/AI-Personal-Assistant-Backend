import os
import sys
import unittest
import tempfile
import shutil
import json
import time

# Set path to root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory
from src.CoreFunctions.Infrastructure import vector_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, delete_vector_fact, rebuild_general_vector_store, _load_data

class TestRefactoredMemory(unittest.TestCase):
    def setUp(self):
        print(f"\n🧪 [TEST RUNNING] {self._testMethodName}...")
        # Use a temporary database file for isolation
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_cache.db")
        
        # Override paths in vector_memory
        from src.CoreFunctions.Infrastructure import vector_memory
        self.original_index_path = vector_memory.INDEX_PATH
        self.original_data_path = vector_memory.DATA_PATH
        self.original_metadata_path = vector_memory.METADATA_PATH
        
        vector_memory.INDEX_PATH = os.path.join(self.test_dir, "index.faiss")
        vector_memory.DATA_PATH = os.path.join(self.test_dir, "data.json")
        vector_memory.METADATA_PATH = os.path.join(self.test_dir, "metadata.json")
        
        # Override environment variables to force SQLite during tests
        self.original_env = {
            "DATABASE_PROVIDER": os.environ.get("DATABASE_PROVIDER"),
            "REDIS_URL": os.environ.get("REDIS_URL"),
            "DATABASE_URL": os.environ.get("DATABASE_URL")
        }
        os.environ["DATABASE_PROVIDER"] = "sqlite"
        if "REDIS_URL" in os.environ:
            del os.environ["REDIS_URL"]
        if "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]
        
        # Reset UnifiedMemory singleton
        self.original_db_path = UnifiedMemory().db_path
        UnifiedMemory._instance = None
        self.um = UnifiedMemory(db_path=self.db_path)

    def tearDown(self):
        # Restore original paths in vector_memory
        from src.CoreFunctions.Infrastructure import vector_memory
        vector_memory.INDEX_PATH = self.original_index_path
        vector_memory.DATA_PATH = self.original_data_path
        vector_memory.METADATA_PATH = self.original_metadata_path
        
        # Restore environment variables
        for k, v in self.original_env.items():
            if v is None:
                if k in os.environ:
                    del os.environ[k]
            else:
                os.environ[k] = v
        
        # Reset UnifiedMemory singleton
        UnifiedMemory._instance = None
        shutil.rmtree(self.test_dir)
        print(f"✅ [TEST FINISHED] {self._testMethodName} completed successfully.\n")

    def test_crm_people_table(self):
        # Insert connection details
        self.um.upsert_person("Rohan", "brother", "rohan@example.com", "12345678", "Student at college")
        self.um.upsert_person("Alice", "friend", "alice@example.com", "", "Colleague")

        # Query connections
        people = self.um.query_people()
        self.assertEqual(len(people), 2)
        
        rohan_info = self.um.query_people(name="Rohan")[0]
        self.assertEqual(rohan_info["relation"], "brother")
        self.assertEqual(rohan_info["email"], "rohan@example.com")
        self.assertEqual(rohan_info["notes"], "Student at college")

        # Filter by relation
        friends = self.um.query_people(relation="friend")
        self.assertEqual(len(friends), 1)
        self.assertEqual(friends[0]["name"], "Alice")

    def test_canonical_profile_table(self):
        # Upsert canonical fields
        self.um.upsert_profile("name", "Prithvi", "stated")
        self.um.upsert_profile("email", "testing_user@example.com", "derived")

        # Query profile
        profile = self.um.query_profile()
        self.assertEqual(len(profile), 2)

        email_fact = self.um.query_profile(key="email")[0]
        self.assertEqual(email_fact["value"], "testing_user@example.com")
        self.assertEqual(email_fact["source"], "derived")

    def test_profile_review_queue(self):
        # Add unrecognized updates
        self.um.add_to_profile_review("major", "computer science", "stated")
        self.um.add_to_profile_review("pet_name", "Max", "inferred")

        # Query review queue
        queue = self.um.query_profile_review()
        self.assertEqual(len(queue), 2)
        self.assertEqual(queue[0]["key"], "major")
        self.assertEqual(queue[1]["source"], "inferred")

        # Resolve one item
        self.um.delete_from_profile_review(queue[0]["id"])
        
        queue_after = self.um.query_profile_review()
        self.assertEqual(len(queue_after), 1)
        self.assertEqual(queue_after[0]["key"], "pet_name")

    def test_timeline_events(self):
        # Log timeline events
        self.um.log_event("task_completion", "Refactored memory SQLite schema", "commit_xyz")
        time.sleep(0.01)
        self.um.log_event("meeting", "Aligned on code design", "")

        # Query events
        events = self.um.query_events()
        self.assertEqual(len(events), 2)
        
        # Latest first
        self.assertEqual(events[0]["event_type"], "meeting")
        self.assertEqual(events[1]["event_type"], "task_completion")
        self.assertEqual(events[1]["ref_id"], "commit_xyz")

    def test_vector_sql_source_of_truth(self):
        # Store facts
        store_vector("I moved to Bangalore recently", source="stated")
        store_vector("I prefer dark mode in UIs", source="inferred")

        # Verify it writes to SQLite vector_facts
        facts_in_sql = self.um.list_vector_facts()
        self.assertEqual(len(facts_in_sql), 2)
        self.assertEqual(facts_in_sql[0]["fact"], "I moved to Bangalore recently")
        self.assertEqual(facts_in_sql[0]["source"], "stated")
        self.assertEqual(facts_in_sql[1]["source"], "inferred")

        # Delete a fact
        delete_vector_fact("I moved to Bangalore recently")

        # Verify deletion cascades to SQL
        facts_after_delete = self.um.list_vector_facts()
        self.assertEqual(len(facts_after_delete), 1)
        self.assertEqual(facts_after_delete[0]["fact"], "I prefer dark mode in UIs")

        # Now force wipe general vector files (data.json and index.faiss)
        os.remove(vector_memory.DATA_PATH)
        os.remove(vector_memory.INDEX_PATH)

        # Trigger self-healing rebuild from SQL source of truth
        rebuild_general_vector_store()

        # Check if index has been recreated successfully
        restored_facts = _load_data()
        self.assertEqual(len(restored_facts), 1)
        self.assertEqual(restored_facts[0], "I prefer dark mode in UIs")

    def test_memory_injector_node_context(self):
        from src.CoreFunctions.StateGraph.memory_nodes import memory_injector_node
        
        # Populate DB
        self.um.upsert_profile("name", "Prithvi", "stated")
        self.um.upsert_person("Rohan", "brother", "rohan@example.com", "12345678", "Student")
        self.um.log_event("task_completion", "Finished refactoring memory system", "commit_1")
        
        # Run memory injector node
        mock_state = {
            "primary_goal": "Tell my brother Rohan about my preferences",
            "working_memory": {}
        }
        
        output_state = memory_injector_node(mock_state)
        working_memory = output_state.get("working_memory", {})
        user_profile = working_memory.get("user_profile", {})
        
        # Verify injected details on personal query
        self.assertEqual(user_profile.get("name"), "Prithvi")
        self.assertIn("Rohan", user_profile.get("social_connections", ""))
        self.assertIn("brother", user_profile.get("social_connections", ""))
        self.assertIn("Finished refactoring memory system", user_profile.get("recent_events", ""))

        # Verify context is ALSO retained on zero-keyword follow-up query (e.g. "so what is it")
        followup_state = {
            "primary_goal": "so what is it (there is contradiction)",
            "working_memory": {}
        }
        followup_output = memory_injector_node(followup_state)
        followup_profile = followup_output.get("working_memory", {}).get("user_profile", {})
        self.assertEqual(followup_profile.get("name"), "Prithvi")
        self.assertIn("Rohan", followup_profile.get("social_connections", ""))

    def test_denials_and_deletions_purging(self):
        # We will mock the reflection LLM output to simulate user telling assistant to remove incorrect github username
        from src.CoreFunctions.StateGraph.memory_nodes import reflection_node
        
        # Populate SQLite vector table with incorrect github username facts
        store_vector("Prithviraj's GitHub handle is eprithvi22", source="stated")
        store_vector("User's GitHub username is eprithvi22 and name is PRITHVIRAJ E.", source="stated")
        
        # Verify they are in SQL
        facts = self.um.list_vector_facts()
        self.assertEqual(len(facts), 2)
        
        # Create a mock reflection response
        class MockMemoryReflection:
            canonical_updates = {}
            unrecognized_updates = {}
            people_updates = []
            events = []
            new_skills = []
            vector_memories = [] # Should NOT save a new fact saying "User requested removal"
            superseded_facts = [
                "Prithviraj's GitHub handle is eprithvi22",
                "User's GitHub username is eprithvi22 and name is PRITHVIRAJ E."
            ] # Purges the wrong facts
            
        class MockLLM:
            def with_structured_output(self, schema):
                class Invoker:
                    def invoke(self, messages):
                        return MockMemoryReflection()
                return Invoker()
                
        # Run reflection node using the mock LLM
        state = {
            "primary_goal": "Remove any association with the GitHub username eprithvi22",
            "completed_tasks": [],
            "final_response": "I have removed all references and associations to the GitHub username eprithvi22.",
            "working_memory": {}
        }
        
        from src.CoreFunctions.Infrastructure import llm_factory
        original_get_llm = llm_factory.get_llm
        llm_factory.get_llm = lambda: MockLLM()
        try:
            reflection_node(state)
        finally:
            llm_factory.get_llm = original_get_llm
        
        # Verify facts were purged from SQLite vector table
        facts_after = self.um.list_vector_facts()
        self.assertEqual(len(facts_after), 0)

    def test_topic_based_stale_fact_purging(self):
        # We will mock the reflection LLM output to simulate user getting their github username verified.
        # The reflection output contains the correct fact, and in superseded_facts, it includes
        # both the old incorrect guess and the intermediate denial fact.
        from src.CoreFunctions.StateGraph.memory_nodes import reflection_node
        
        # Populate SQLite with the old guess, the intermediate denial, and the correct handle
        store_vector("User's GitHub username is eprithvi22", source="stated")
        store_vector("User is NOT associated with GitHub username 'eprithvi22'", source="stated")
        
        # Verify initial size
        facts = self.um.list_vector_facts()
        self.assertEqual(len(facts), 2)
        
        # Create mock reflection output
        class MockMemoryReflection:
            canonical_updates = {}
            unrecognized_updates = {}
            people_updates = []
            events = []
            new_skills = []
            vector_memories = [
                # New verified fact
                type('ProfileFact', (object,), {"value": "The user's verified GitHub username is PrithvirajSinghChauhan8444.", "source": "derived"})()
            ]
            superseded_facts = [
                "User's GitHub username is eprithvi22",
                "User is NOT associated with GitHub username 'eprithvi22'"
            ] # Purges the wrong facts and the denial
            
        class MockLLM:
            def with_structured_output(self, schema):
                class Invoker:
                    def invoke(self, messages):
                        return MockMemoryReflection()
                return Invoker()
                
        # Run reflection node
        state = {
            "primary_goal": "verify my correct github handle from account profile data",
            "completed_tasks": [],
            "final_response": "I verified your handle is PrithvirajSinghChauhan8444.",
            "working_memory": {}
        }
        
        from src.CoreFunctions.Infrastructure import llm_factory
        original_get_llm = llm_factory.get_llm
        llm_factory.get_llm = lambda: MockLLM()
        try:
            reflection_node(state)
        finally:
            llm_factory.get_llm = original_get_llm
            
        # Verify only the single verified fact remains
        facts_after = self.um.list_vector_facts()
        self.assertEqual(len(facts_after), 1)
        self.assertEqual(facts_after[0]["fact"], "The user's verified GitHub username is PrithvirajSinghChauhan8444.")

if __name__ == '__main__':
    unittest.main()
