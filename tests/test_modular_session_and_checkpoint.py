import os
import json
import unittest
from unittest.mock import patch

from modules.infrastructure.storage.session_manager import (
    save_interrupted_task_checkpoint,
    clear_interrupted_task_checkpoint,
    get_interrupted_task,
    save_session_context,
    load_session_context,
    clear_session_context,
    archive_chat_turn,
    SESSION_CONTEXT_PATH,
    INTERRUPTED_TASK_PATH,
    CHAT_ARCHIVE_PATH
)
from modules.infrastructure.security.oauth import (
    load_google_accounts,
    resolve_expected_email
)
from modules.integration.application_orchestrator import ApplicationOrchestrator

class TestModularSessionAndCheckpoint(unittest.TestCase):
    def setUp(self):
        clear_interrupted_task_checkpoint()
        clear_session_context()

    def tearDown(self):
        clear_interrupted_task_checkpoint()
        clear_session_context()

    def test_interrupted_task_checkpoint_lifecycle(self):
        sample_state = {
            "primary_goal": "Download class syllabus and email professor",
            "active_subtasks": [{"id": "t1", "status": "in_progress", "assigned_worker": "ClassroomWorker"}],
            "working_memory": {
                "active_skills": ["transient_skill"],
                "saved_fact": "Due next Tuesday"
            },
            "completed_tasks": {"t0": {"status": "completed", "summary": "Found course"}},
            "chat_history": [{"role": "user", "content": "Get syllabus"}]
        }

        save_interrupted_task_checkpoint(sample_state, status="running")
        self.assertTrue(os.path.exists(INTERRUPTED_TASK_PATH))

        data = get_interrupted_task()
        self.assertIsNotNone(data)
        self.assertEqual(data["primary_goal"], "Download class syllabus and email professor")
        self.assertEqual(data["status"], "running")
        # Transient key filtered
        self.assertNotIn("active_skills", data["working_memory"])
        self.assertEqual(data["working_memory"]["saved_fact"], "Due next Tuesday")

        clear_interrupted_task_checkpoint()
        self.assertFalse(os.path.exists(INTERRUPTED_TASK_PATH))
        self.assertIsNone(get_interrupted_task())

    def test_session_context_save_and_load(self):
        history = [
            {"role": "user", "content": "What is on my calendar?"},
            {"role": "assistant", "content": "You have a meeting at 2 PM."}
        ]
        wm = {"user_profile": {"name": "Test User"}, "relevant_memories": ["transient"]}
        completed = {"task_cal": {"summary": "Retrieved 1 meeting"}}

        save_session_context(
            chat_history=history,
            working_memory=wm,
            completed_tasks=completed,
            session_summary="Calendar overview",
            session_id="test_session_1"
        )
        self.assertTrue(os.path.exists(SESSION_CONTEXT_PATH))

        loaded = load_session_context()
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded["chat_history"]), 2)
        self.assertEqual(loaded["session_summary"], "Calendar overview")
        self.assertNotIn("relevant_memories", loaded["working_memory"])

        clear_session_context()
        self.assertFalse(os.path.exists(SESSION_CONTEXT_PATH))

    def test_dynamic_account_grounding_resolution(self):
        accounts = load_google_accounts()
        self.assertIsInstance(accounts, dict)
        if "personal" in accounts and accounts["personal"]:
            email = resolve_expected_email("personal")
            self.assertEqual(email, accounts["personal"].lower())

        with self.assertRaises(ValueError) as ctx:
            resolve_expected_email("non_existent_unmapped_alias")
        self.assertIn("Available configured accounts:", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
