import unittest
import json
import os
from unittest.mock import patch

from src.CoreFunctions.Infrastructure.auth_utils import (
    load_google_accounts,
    resolve_expected_email,
)
from src.CoreFunctions.StateGraph.Workers.ClassroomWorker.classroom_worker_tools.classroom_worker_tool_fetch_courses import (
    fetch_classroom_courses,
)
from src.CoreFunctions.StateGraph.memory_nodes import memory_injector_node


class TestDynamicAccountGrounding(unittest.TestCase):

    def test_resolve_expected_email_success(self):
        """Verify that known configured aliases and raw emails resolve correctly."""
        # Raw email
        self.assertEqual(resolve_expected_email("test@example.com"), "test@example.com")

        # Configured alias (from actual google_accounts.json)
        accounts = load_google_accounts()
        if "personal" in accounts and accounts["personal"]:
            self.assertEqual(resolve_expected_email("personal"), accounts["personal"].lower())
        if "college" in accounts and accounts["college"]:
            self.assertEqual(resolve_expected_email("college"), accounts["college"].lower())

    def test_resolve_expected_email_unmapped_raises_value_error_non_blocking(self):
        """Verify that an unmapped alias raises a dynamic ValueError with available accounts and does NOT block on input()."""
        # Ensure stdin is not called even if someone tries
        with patch("builtins.input", side_effect=AssertionError("input() must NEVER be called")):
            with self.assertRaises(ValueError) as ctx:
                resolve_expected_email("non_existent_alias_xyz_123")
            
            err_msg = str(ctx.exception)
            self.assertIn("non_existent_alias_xyz_123", err_msg)
            self.assertIn("Available configured accounts:", err_msg)

    def test_fetch_courses_tool_returns_diagnostic_error_on_invalid_account(self):
        """Verify that when a tool is called with an invalid alias, it returns the error string to the LLM agent."""
        res = fetch_classroom_courses(account="arbitrary_unknown_account")
        self.assertIn("Error listing courses", res)
        self.assertIn("arbitrary_unknown_account", res)
        self.assertIn("Available configured accounts:", res)

    def test_memory_injector_injects_configured_accounts(self):
        """Verify that memory_injector_node injects configured_accounts into user_profile."""
        state = {
            "primary_goal": "check upcoming coursework deadlines",
            "working_memory": {}
        }
        output = memory_injector_node(state)
        wm = output.get("working_memory", {})
        user_profile = wm.get("user_profile", {})
        
        accounts = load_google_accounts()
        active_accounts = {k: v for k, v in accounts.items() if v and str(v).strip()}
        if active_accounts:
            self.assertIn("configured_accounts", user_profile)
            self.assertEqual(user_profile["configured_accounts"], active_accounts)
            self.assertIn("active_account_aliases", user_profile)


if __name__ == "__main__":
    unittest.main()
