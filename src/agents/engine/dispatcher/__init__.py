"""Polyglot Tool Dispatcher Subsystem with Single-Responsibility Submodules."""

from src.agents.engine.dispatcher.dispatcher import ToolDispatcher
from src.agents.engine.dispatcher.extractor import IntentExtractor
from src.agents.engine.dispatcher.go_executor import GoToolExecutor
from src.agents.engine.dispatcher.mcp_executor import MCPToolExecutor
from src.agents.engine.dispatcher.python_executor import PythonToolExecutor
from src.agents.engine.dispatcher.router import DomainRouter
from src.agents.engine.dispatcher.types import (
    MCPClientProtocol,
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
