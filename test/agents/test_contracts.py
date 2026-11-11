"""Tests for Layer 6 Agent contracts and schemas."""

from src.agents.contracts import (
    AgentContext,
    AgentTurnResult,
    AgentType,
    ToolCallIntent,
    ToolCallResult,
    ToolDefinition,
)


def test_agent_type_enum() -> None:
    assert AgentType.MANAGER.value == "manager"
    assert AgentType.SYSTEM.value == "system"
    assert AgentType.RESEARCH.value == "research"
    assert AgentType.BROWSER.value == "browser"
    assert AgentType.PRODUCTIVITY.value == "productivity"


def test_tool_definition_to_dict() -> None:
    tool = ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        risk="LOW",
    )
    schema = tool.to_dict()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "test_tool"
    assert schema["function"]["description"] == "A test tool"
    assert "query" in schema["function"]["parameters"]["properties"]


def test_tool_call_intent_to_dict() -> None:
    intent = ToolCallIntent(
        call_id="call_001",
        tool_name="fs_read",
        arguments={"path": "README.md"},
    )
    d = intent.to_dict()
    assert d["id"] == "call_001"
    assert d["type"] == "function"
    assert d["function"]["name"] == "fs_read"
    assert d["function"]["arguments"]["path"] == "README.md"


def test_agent_context_and_turn_result_defaults() -> None:
    ctx = AgentContext(
        session_id="s1",
        turn_id="t1",
        agent_type=AgentType.SYSTEM,
        user_prompt="Hello",
        system_prompt="System instructions",
    )
    assert ctx.max_iterations == 10
    assert ctx.conversation_history == []
    assert ctx.available_tools == []

    res = AgentTurnResult(status="success", final_response="Done")
    assert res.iterations_used == 0
    assert res.tool_calls_executed == 0
    assert res.subtask_results == []
