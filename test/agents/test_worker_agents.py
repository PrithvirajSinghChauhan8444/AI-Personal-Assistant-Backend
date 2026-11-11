"""Tests for specialized worker agents."""

from typing import Any, AsyncIterator, Dict, List, Optional
import pytest

from src.agents.browser.agent import BrowserAgent
from src.agents.contracts import AgentType
from src.agents.productivity.agent import ProductivityAgent
from src.agents.research.agent import ResearchAgent
from src.agents.system.agent import SystemAgent
from src.models.base import BaseLLMClient
from src.models.types import StreamChunk


class SimpleMockLLM(BaseLLMClient):
    def __init__(self, reply: str) -> None:
        super().__init__(model_name="simple-mock")
        self.reply = reply

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(text_delta=self.reply)


@pytest.mark.asyncio
async def test_system_agent() -> None:
    llm = SimpleMockLLM("System operation executed.")
    agent = SystemAgent(model_client=llm)

    assert agent.agent_type == AgentType.SYSTEM
    tool_names = [t.name for t in agent.tools]
    assert "sys_exec" in tool_names
    assert "fs_read" in tool_names
    assert "git_status" in tool_names

    res = await agent.execute_turn(session_id="s1", turn_id="t1", prompt="List directory")
    assert res.status == "success"
    assert res.final_response == "System operation executed."


@pytest.mark.asyncio
async def test_research_agent() -> None:
    llm = SimpleMockLLM("Research findings synthesized.")
    agent = ResearchAgent(model_client=llm)

    assert agent.agent_type == AgentType.RESEARCH
    tool_names = [t.name for t in agent.tools]
    assert "net_search" in tool_names
    assert "net_fetch" in tool_names
    assert "memory_search" in tool_names
    assert "memory_store_fact" in tool_names

    res = await agent.execute_turn(session_id="s1", turn_id="t1", prompt="Search web for facts")
    assert res.status == "success"
    assert res.final_response == "Research findings synthesized."


@pytest.mark.asyncio
async def test_browser_agent() -> None:
    llm = SimpleMockLLM("Browser page navigated.")
    agent = BrowserAgent(model_client=llm)

    assert agent.agent_type == AgentType.BROWSER
    tool_names = [t.name for t in agent.tools]
    assert "browser_navigate" in tool_names
    assert "browser_click" in tool_names
    assert "browser_screenshot" in tool_names

    res = await agent.execute_turn(session_id="s1", turn_id="t1", prompt="Open website")
    assert res.status == "success"
    assert res.final_response == "Browser page navigated."


@pytest.mark.asyncio
async def test_productivity_agent() -> None:
    llm = SimpleMockLLM("Emails checked.")
    agent = ProductivityAgent(model_client=llm)

    assert agent.agent_type == AgentType.PRODUCTIVITY
    tool_names = [t.name for t in agent.tools]
    assert "gmail_list" in tool_names
    assert "gmail_read" in tool_names
    assert "gmail_send_draft" in tool_names
    assert "calendar_list" in tool_names

    res = await agent.execute_turn(session_id="s1", turn_id="t1", prompt="Check inbox")
    assert res.status == "success"
    assert res.final_response == "Emails checked."
