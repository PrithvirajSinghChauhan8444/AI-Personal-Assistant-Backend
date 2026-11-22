"""Base Agent modular subsystem components.

File names:
  - base.py           -> BaseAgent (main standard base agent)
  - ToolRegistry.py   -> ToolRegistry & RISK_ORDER (tool catalog & risk tiers)
  - PromptManager.py  -> PromptManager (persona & system prompt management)
  - ContextBuilder.py -> ContextBuilder (turn context assembly & validation)
  - AgentHooks.py     -> AgentHooks & AgentLifecycle (turn execution lifecycle hooks & error capture)
  - AgentValidator.py -> AgentValidator, validate_agent_configuration, infer_agent_name, describe_agent
"""

from src.agents.Base.AgentHooks import AgentHooks, AgentLifecycle
from src.agents.Base.AgentValidator import (
    AgentValidator,
    describe_agent,
    infer_agent_name,
    validate_agent_configuration,
)
from src.agents.Base.ContextBuilder import ContextBuilder
from src.agents.Base.PromptManager import PromptManager
from src.agents.Base.ToolRegistry import RISK_ORDER, ToolRegistry
from src.agents.Base.base import BaseAgent

__all__ = [
    "AgentHooks",
    "AgentLifecycle",
    "AgentValidator",
    "BaseAgent",
    "ContextBuilder",
    "PromptManager",
    "RISK_ORDER",
    "ToolRegistry",
    "describe_agent",
    "infer_agent_name",
    "validate_agent_configuration",
]
