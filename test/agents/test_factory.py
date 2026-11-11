"""Tests for Layer 6 Specialist Worker Agent factory functions."""

from src.agents.contracts import AgentType
from src.agents.factory import create_agent, create_all_agents
from src.agents.system.agent import SystemAgent
from src.models.base import BaseLLMClient
from src.models.types import StreamChunk
from typing import Any, AsyncIterator, Dict, List, Optional


class DummyLLM(BaseLLMClient):
    def __init__(self) -> None:
        super().__init__(model_name="dummy")

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(text_delta="dummy")


def test_create_agent_individual() -> None:
    llm = DummyLLM()
    system_agent = create_agent(AgentType.SYSTEM, model_client=llm)
    assert isinstance(system_agent, SystemAgent)
    assert system_agent.agent_type == AgentType.SYSTEM


def test_create_all_agents_wiring() -> None:
    llm = DummyLLM()
    agents = create_all_agents(model_client=llm)

    assert len(agents) == 4
    assert AgentType.SYSTEM in agents
    assert AgentType.RESEARCH in agents
    assert AgentType.BROWSER in agents
    assert AgentType.PRODUCTIVITY in agents
