"""Isolated integration test for BrowserAgent with Playwright MCP Server."""

import pytest
from src.agents.browser.agent import BrowserAgent
from src.agents.browser.mcp_bridge import PlaywrightMCPBridge
from src.agents.contracts import AgentType, ToolCallIntent
from src.models.base import BaseLLMClient
from src.models.types import StreamChunk, ToolCallChunk
from typing import Any, AsyncIterator, Dict, List, Optional


class MockIsolatedBrowserLLM(BaseLLMClient):
    """Deterministic LLM for testing isolated browser agent turns."""

    def __init__(self) -> None:
        super().__init__(model_name="mock-isolated-browser")
        self.turns = 0

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[StreamChunk]:
        self.turns += 1

        if self.turns == 1:
            yield StreamChunk(thought="Navigating to target test URL using Playwright MCP...")
            yield StreamChunk(
                tool_calls=[
                    ToolCallChunk(
                        call_id="call_1",
                        tool_name="browser_navigate",
                        arguments_json='{"url": "https://example.com"}',
                    )
                ]
            )
        elif self.turns == 2:
            yield StreamChunk(thought="Taking snapshot of loaded webpage...")
            yield StreamChunk(
                tool_calls=[
                    ToolCallChunk(
                        call_id="call_2",
                        tool_name="browser_snapshot",
                        arguments_json="{}",
                    )
                ]
            )
        else:
            yield StreamChunk(text_delta="Verified page heading is 'Example Domain' via Playwright MCP.")


@pytest.mark.asyncio
async def test_playwright_mcp_bridge_isolated():
    """Verifies that PlaywrightMCPBridge spawns Brave with --isolated and runs RPC commands."""
    bridge = PlaywrightMCPBridge(isolated=True, headless=True)
    try:
        bridge.start()
        assert bridge._proc is not None

        # Execute navigation
        res_nav = await bridge.execute_tool("browser_navigate", {"url": "https://example.com"}, "call_nav")
        assert not res_nav.is_error

        # Execute snapshot
        res_snap = await bridge.execute_tool("browser_snapshot", {}, "call_snap")
        assert not res_snap.is_error
        assert "Example Domain" in res_snap.output or "page.goto" in res_snap.output
    finally:
        bridge.stop()
        assert bridge._proc is None


@pytest.mark.asyncio
async def test_browser_agent_isolated_turn():
    """Verifies BrowserAgent running full ReAct loop against PlaywrightMCPBridge."""
    llm = MockIsolatedBrowserLLM()
    agent = BrowserAgent(model_client=llm)
    bridge = PlaywrightMCPBridge(isolated=True, headless=True)

    class IntentCaptureEmitter:
        def __init__(self, target_bridge):
            self.target_bridge = target_bridge

        async def emit_thought(self, turn_id: str, agent_name: str, thought: str):
            pass

        async def emit_token(self, turn_id: str, agent_name: str, token: str):
            pass

        async def emit_tool_call(self, turn_id: str, intent: ToolCallIntent):
            self.target_bridge.queue_intent(intent)

        async def emit_status(self, turn_id: str, agent_name: str, status_msg: str):
            pass

    emitter = IntentCaptureEmitter(bridge)

    try:
        bridge.start()
        res = await agent.execute_turn(
            session_id="test_session_isolated",
            turn_id="test_turn_isolated",
            prompt="Navigate to https://example.com and check heading",
            pipe_emitter=emitter,
            pipe_reader=bridge,
            max_iterations=5,
        )

        assert res.status == "success"
        assert "Example Domain" in res.final_response
        assert res.tool_calls_executed == 2
    finally:
        bridge.stop()
