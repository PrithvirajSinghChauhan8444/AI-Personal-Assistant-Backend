import os
import sys
import unittest
import tempfile
import shutil
import json
import hashlib
from unittest.mock import MagicMock, patch

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector, delete_vector_fact, rebuild_skills_vector_store, search_skills_vector
from src.CoreFunctions.StateGraph.task_router import task_router_node
from src.CoreFunctions.StateGraph.executor import _run_ephemeral_agent, _get_worker_feedback_instructions

class TestArchitectureRefinement(unittest.TestCase):
    def setUp(self):
        # Isolation directory
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_cache.db")
        
        # Override UnifiedMemory singleton
        self.original_db_path = UnifiedMemory().db_path
        UnifiedMemory._instance = None
        self.um = UnifiedMemory(db_path=self.db_path)
        
        # Override Vector Store paths
        import src.CoreFunctions.Infrastructure.vector_memory as vm
        self.original_vm_index = vm.INDEX_PATH
        self.original_vm_data = vm.DATA_PATH
        self.original_skills_index = vm.SKILLS_INDEX_PATH
        self.original_skills_data = vm.SKILLS_DATA_PATH
        
        vm.INDEX_PATH = os.path.join(self.test_dir, "index.faiss")
        vm.DATA_PATH = os.path.join(self.test_dir, "data.json")
        vm.SKILLS_INDEX_PATH = os.path.join(self.test_dir, "skills_index.faiss")
        vm.SKILLS_DATA_PATH = os.path.join(self.test_dir, "skills_data.json")
        
    def tearDown(self):
        UnifiedMemory._instance = None
        
        import src.CoreFunctions.Infrastructure.vector_memory as vm
        vm.INDEX_PATH = self.original_vm_index
        vm.DATA_PATH = self.original_vm_data
        vm.SKILLS_INDEX_PATH = self.original_skills_index
        vm.SKILLS_DATA_PATH = self.original_skills_data
        
        shutil.rmtree(self.test_dir)

    @patch("langchain_google_genai.ChatGoogleGenerativeAI.invoke")
    def test_task_router_self_correction_and_fallback(self, mock_invoke):
        from langchain_core.messages import AIMessage
        
        args_data = {
            "subtasks": [
                {
                    "id": "task_1",
                    "description": "Test task",
                    "assigned_worker": "MiscWorker",
                    "depends_on": []
                }
            ]
        }
        tool_call = {
            "name": "TaskPlan",
            "args": args_data,
            "id": "call_1",
            "type": "tool_call"
        }
        json_content = json.dumps(args_data)
        mock_msg = AIMessage(content=json_content, tool_calls=[tool_call])
        
        # First call raises exception, second call returns valid message which is parsed correctly
        mock_invoke.side_effect = [
            Exception("Simulated Validation Mismatch"),
            mock_msg
        ]
        
        state = {
            "primary_goal": "Please run a test task",
            "active_subtasks": [],
            "working_memory": {},
            "completed_tasks": {},
            "final_response": "",
            "chat_history": []
        }
        
        output = task_router_node(state)
        
        self.assertEqual(mock_invoke.call_count, 2)
        self.assertEqual(len(output["active_subtasks"]), 1)
        self.assertEqual(output["active_subtasks"][0]["id"], "task_1")

    @patch("langchain_google_genai.ChatGoogleGenerativeAI.invoke")
    def test_task_router_fallback_on_double_failure(self, mock_invoke):
        # Simulate failures on BOTH attempts
        mock_invoke.side_effect = Exception("Permanent Validation Error")
        
        state = {
            "primary_goal": "Please run a test task",
            "active_subtasks": [],
            "working_memory": {},
            "completed_tasks": {},
            "final_response": "",
            "chat_history": []
        }
        
        output = task_router_node(state)
        
        # Should invoke twice and then fall back to MiscWorker gracefully
        self.assertEqual(mock_invoke.call_count, 2)
        self.assertEqual(len(output["active_subtasks"]), 1)
        self.assertEqual(output["active_subtasks"][0]["assigned_worker"], "MiscWorker")
        self.assertIn("Fallback", output["active_subtasks"][0]["description"])

    def test_vector_tombstoning_on_memory_update(self):
        # 1. Store a memory fact
        store_memory("user", "favorite_color", "Red")
        # Store corresponding vector memory fact
        fact = "The user's favorite color is Red."
        store_vector(fact)
        
        # Verify vector fact exists
        results_before = search_vector("favorite color", k=1)
        self.assertIn(fact, results_before)
        
        # 2. Update memory fact (triggers Vector Tombstoning)
        # Patch delete_vector_fact inside vector_memory because memory.py dynamically imports it
        with patch("src.CoreFunctions.Infrastructure.vector_memory.delete_vector_fact", wraps=delete_vector_fact) as mock_delete:
            store_memory("user", "favorite_color", "Blue")
            
            # Assert delete_vector_fact was called with the old value "Red"
            mock_delete.assert_called_with("Red")
            
        # Re-search the vector store for "Red" to confirm it is deleted
        self.assertNotIn("Red", search_vector("favorite color", k=1))

    def test_user_feedback_loop_injection_and_cleanup(self):
        worker_name = "MiscWorker"
        db_key = f"worker_feedback:{worker_name}"
        
        # 1. Store a 'once' scope preference
        self.um.store_memory(db_key, {
            "preferences": [
                {"preference": "Start response with 'Greeting Chief'", "scope": "once", "timestamp": 12345}
            ]
        })
        
        # 2. Retrieve instructions (which should trigger once-cleanup)
        instructions = _get_worker_feedback_instructions(worker_name)
        self.assertIn("Greeting Chief", instructions)
        
        # 3. Verify it is cleaned up / deleted from database since scope was 'once'
        self.assertIsNone(self.um.retrieve_memory(db_key))
        
        # 4. Store a 'persistent' scope preference
        self.um.store_memory(db_key, {
            "preferences": [
                {"preference": "Always use professional tone", "scope": "persistent", "timestamp": 12345}
            ]
        })
        
        # 5. Retrieve instructions
        instructions_persistent = _get_worker_feedback_instructions(worker_name)
        self.assertIn("Always use professional tone", instructions_persistent)
        
        # 6. Verify it remains in database because scope is persistent
        self.assertIsNotNone(self.um.retrieve_memory(db_key))

    def test_skills_index_md5_drift_check(self):
        # Mock rebuilding skills store
        import src.CoreFunctions.Infrastructure.vector_memory as vm
        
        # Create a mock skill directory and SKILL.md file in test_dir
        skills_dir = os.path.join(self.test_dir, "Skills")
        skill_folder = os.path.join(skills_dir, "productivity", "test-skill")
        os.makedirs(skill_folder, exist_ok=True)
        skill_path = os.path.join(skill_folder, "SKILL.md")
        
        skill_content = """---
name: test-skill
description: "A temporary verification skill."
category: productivity
tags: [temp, test]
---
# Test Skill Procedure
1. Step 1.
"""
        with open(skill_path, "w") as f:
            f.write(skill_content)
            
        # Temporarily point BASE_DIR in vector_memory to our test_dir
        original_base_dir = vm.BASE_DIR
        vm.BASE_DIR = self.test_dir
        
        try:
            # Rebuild vector store
            rebuild_skills_vector_store()
            
            # Verify file exists
            self.assertTrue(os.path.exists(vm.SKILLS_INDEX_PATH))
            
            # Check search executes with no rebuild (stale_found = False)
            with patch("src.CoreFunctions.Infrastructure.vector_memory.rebuild_skills_vector_store", wraps=rebuild_skills_vector_store) as mock_rebuild:
                results = search_skills_vector("temporary verification", k=1)
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["name"], "test-skill")
                # Rebuild should NOT have been triggered because hashes match
                mock_rebuild.assert_not_called()
                
            # Now modify the SKILL.md file content to trigger hash mismatch (drift)
            with open(skill_path, "w") as f:
                f.write(skill_content + "\n# Modified Line to trigger hash mismatch.")
                
            # Check search executes and triggers automatic rebuild
            with patch("src.CoreFunctions.Infrastructure.vector_memory.rebuild_skills_vector_store", wraps=rebuild_skills_vector_store) as mock_rebuild_drift:
                results_drift = search_skills_vector("temporary verification", k=1)
                self.assertEqual(len(results_drift), 1)
                # Rebuild SHOULD have been triggered due to hash drift
                mock_rebuild_drift.assert_called_once()
                
        finally:
            vm.BASE_DIR = original_base_dir

if __name__ == '__main__':
    unittest.main()
