import os
import sys
import json
import unittest
import shutil
import threading
from unittest.mock import patch

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.StateGraph.registry import WorkerRegistry, scan_and_register_workers
from src.CoreFunctions.StateGraph.executor import _update_state_completed
from src.CoreFunctions.vector_memory import search_skills_vector, rebuild_skills_vector_store

class TestPlugAndPlay(unittest.TestCase):
    def setUp(self):
        scan_and_register_workers()
        self.config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
        self.config_path = os.path.join(self.config_dir, "workers_config.json")
        self.backup_path = self.config_path + ".bak"
        if os.path.exists(self.config_path):
            os.replace(self.config_path, self.backup_path)

    def tearDown(self):
        if os.path.exists(self.backup_path):
            os.replace(self.backup_path, self.config_path)
        elif os.path.exists(self.config_path):
            os.remove(self.config_path)
        WorkerRegistry._config = {}

    def test_dynamic_active_list(self):
        # 1. Start with SystemWorker inactive, GmailWorker active
        test_config = {
            "SystemWorker": {"model": "gemini-3.1-flash-lite", "active": False},
            "GmailWorker": {"model": "gemini-3.1-flash-lite", "active": True}
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(test_config, f, indent=4)

        scan_and_register_workers(force_reload=True)

        # get_all_workers should dynamic load it
        active_names = WorkerRegistry.get_worker_names()
        self.assertNotIn("SystemWorker", active_names)
        self.assertIn("GmailWorker", active_names)

        # 2. Modify config to enable SystemWorker and disable GmailWorker
        test_config["SystemWorker"]["active"] = True
        test_config["GmailWorker"]["active"] = False
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(test_config, f, indent=4)

        scan_and_register_workers(force_reload=True)

        # get_all_workers should load the updated config dynamically
        active_names_updated = WorkerRegistry.get_worker_names()
        self.assertIn("SystemWorker", active_names_updated)
        self.assertNotIn("GmailWorker", active_names_updated)

    def test_update_state_completed_returns_single_subtask(self):
        state = {
            "active_subtasks": [
                {"id": "task_1", "assigned_worker": "GmailWorker", "status": "in_progress", "description": "task 1", "depends_on": []},
                {"id": "task_2", "assigned_worker": "MemoryWorker", "status": "pending", "description": "task 2", "depends_on": []}
            ],
            "working_memory": {},
            "completed_tasks": {}
        }
        res = _update_state_completed(state, "task_1", "completed data")
        # should only return task_1 in active_subtasks
        self.assertEqual(len(res["active_subtasks"]), 1)
        self.assertEqual(res["active_subtasks"][0]["id"], "task_1")
        self.assertEqual(res["active_subtasks"][0]["status"], "completed")

    def test_vector_memory_self_healing(self):
        # Create a temporary skill file on disk
        skills_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../Skills"))
        temp_skill_folder = os.path.join(skills_dir, "general", "test-temp-skill")
        os.makedirs(temp_skill_folder, exist_ok=True)
        temp_skill_file = os.path.join(temp_skill_folder, "SKILL.md")
        
        skill_md_content = """---
name: test-temp-skill
description: "A temporary skill for verification"
category: general
tags: [temp, verification]
---
# Test Temp Skill
Procedure steps.
"""
        with open(temp_skill_file, "w", encoding="utf-8") as f:
            f.write(skill_md_content)

        try:
            # Rebuild vector store to index the new skill
            rebuild_skills_vector_store()
            
            # Search should find it
            results = search_skills_vector("temporary skill", k=1)
            self.assertTrue(any(s["name"] == "test-temp-skill" for s in results))
            
            # Now delete the file on disk, making the vector store stale
            os.remove(temp_skill_file)
            shutil.rmtree(temp_skill_folder, ignore_errors=True)
            
            # Search again. The self-healing should trigger rebuild_skills_vector_store automatically,
            # reload data, and verify the path doesn't exist, returning empty or other matches.
            results_after = search_skills_vector("temporary skill", k=1)
            self.assertFalse(any(s["name"] == "test-temp-skill" for s in results_after))
        finally:
            shutil.rmtree(temp_skill_folder, ignore_errors=True)
            rebuild_skills_vector_store()

if __name__ == "__main__":
    unittest.main()
