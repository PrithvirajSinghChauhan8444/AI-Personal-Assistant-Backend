"""Autonomous Polyglot Tool Dispatcher Facade.

Re-exports the modular dispatcher subsystem from src.agents.engine.dispatcher.
"""

from src.agents.engine.dispatcher import (
    DomainRouter,
    GoToolExecutor,
    IntentExtractor,
    MCPClientProtocol,
    MCPToolExecutor,
    PythonToolExecutor,
    ToolDispatcher,
    ToolTurnExecutionResult,
)

__all__ = [
    "DomainRouter",
    "GoToolExecutor",
    "IntentExtractor",
    "MCPClientProtocol",
    "MCPToolExecutor",
    "PythonToolExecutor",
    "ToolDispatcher",
    "ToolTurnExecutionResult",
]
