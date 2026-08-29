"""
End-to-End Execution Test for AssistantREPL
Tests both greeting fast-path and full StateGraph routing execution.
"""
import os
import sys

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, WORKSPACE_ROOT)

from src.cli import AssistantREPL

def run_e2e_test():
    print("\n--- [E2E Test 1: Instantiation & Banner] ---")
    repl = AssistantREPL()
    repl.render_banner()

    print("\n--- [E2E Test 2: Fast Greeting Handling] ---")
    handled = repl.handle_fast_greeting("hello")
    assert handled is True, "Fast greeting should be handled"
    assert len(repl.chat_history) >= 2, "Chat history should contain greeting and response"
    print("✔ Greeting fast-path executed and rendered.")

    print("\n--- [E2E Test 3: Full StateGraph Execution] ---")
    test_query = "What is the capital of France and what tools do you have available?"
    print(f"Executing query: {test_query}")
    repl.execute_stategraph_request(test_query)
    
    assert len(repl.chat_history) >= 4, "Chat history should contain user query and final response"
    last_response = repl.chat_history[-1]["content"]
    assert last_response and len(last_response) > 10, "Response should be non-empty"
    print(f"✔ StateGraph execution completed with response length {len(last_response)} characters.")

    print("\n--- [E2E Test 4: Slash Command Handlers] ---")
    for cmd in ["/workers", "/memory", "/graph", "/stats", "/doctor"]:
        res = repl.handle_slash_command(cmd)
        assert res is True, f"Command {cmd} should succeed"
    print("✔ All slash commands executed and rendered successfully.")

    print("\n🎉 ALL END-TO-END CLI TESTS PASSED!")

if __name__ == "__main__":
    run_e2e_test()
