"""Turn execution lifecycle hooks and error management for BaseAgent."""

from __future__ import annotations

from src.agents.contracts import AgentContext, AgentTurnResult


class AgentHooks:
    """Manages pre-turn, post-turn, and error handling hooks for an agent."""

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name

    def before_turn(self, ctx: AgentContext) -> None:
        """Lifecycle hook executed immediately before the turn begins."""
        pass

    def after_turn(self, result: AgentTurnResult, ctx: AgentContext) -> AgentTurnResult:
        """Lifecycle hook executed immediately after turn completion."""
        return result

    def on_turn_error(self, error: Exception, ctx: AgentContext) -> AgentTurnResult:
        """Lifecycle hook to handle unhandled exceptions during execution."""
        return AgentTurnResult(
            status="error",
            final_response=f"Agent '{self.agent_name}' encountered an error: {error}",
            iterations_used=0,
            tool_calls_executed=0,
        )


# Backward-compatible alias
AgentLifecycle = AgentHooks
