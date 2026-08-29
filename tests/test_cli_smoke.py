"""
Smoke test for AssistantREPL (Option B pure CLI)
"""
import os
import sys

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, WORKSPACE_ROOT)

from src.cli import AssistantREPL

def test_repl_initialization():
    repl = AssistantREPL()
    assert repl is not None
    assert repl.session_prompts == 0

    # Test slash commands
    assert repl.handle_slash_command("/workers") is True
    assert repl.handle_slash_command("/memory") is True
    assert repl.handle_slash_command("/graph") is True
    assert repl.handle_slash_command("/stats") is True
    assert repl.handle_slash_command("/history") is True
    assert repl.handle_slash_command("/doctor") is True
    print("\n✔ All REPL smoke tests passed successfully!")

if __name__ == "__main__":
    test_repl_initialization()
