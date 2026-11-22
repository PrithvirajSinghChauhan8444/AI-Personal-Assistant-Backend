"""Domain router determining execution path (Python vs Go vs MCP) for tool calls."""

from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple, Union

from src.agents.contracts import AgentContext, ToolDefinition, ToolExecutionDomain

GO_TOOL_PREFIXES: Tuple[str, ...] = (
    "sys_",
    "fs_",
    "git_",
    "net_",
    "workspace_",
    "hypr_",
    "classroom_",
    "gmail_",
    "calendar_",
    "tasks_",
)


class DomainRouter:
    """Classifies tools into their optimal execution domains."""

    def __init__(
        self,
        domain_overrides: Optional[Dict[str, Union[ToolExecutionDomain, str]]] = None,
        tool_definitions: Optional[Dict[str, ToolDefinition]] = None,
    ) -> None:
        self.domain_overrides: Dict[str, ToolExecutionDomain] = {
            k: ToolExecutionDomain(v) for k, v in (domain_overrides or {}).items()
        }
        self.tool_definitions: Dict[str, ToolDefinition] = dict(tool_definitions or {})

    def register_tool_definition(self, tool: ToolDefinition) -> DomainRouter:
        """Registers a tool definition into the route catalog."""
        self.tool_definitions[tool.name] = tool
        return self

    def unregister_tool_definition(self, tool_name: str) -> bool:
        """Removes a tool definition from the route catalog."""
        return self.tool_definitions.pop(tool_name, None) is not None

    def set_domain_override(
        self, tool_name: str, domain: Union[ToolExecutionDomain, str]
    ) -> DomainRouter:
        """Overrides the execution domain for a specific tool."""
        self.domain_overrides[tool_name] = ToolExecutionDomain(domain)
        return self

    def determine_domain(
        self,
        tool_name: str,
        ctx: Optional[AgentContext] = None,
        has_local_handler: bool = False,
        is_memory_tool: bool = False,
        has_mcp_client: bool = False,
        has_pipe_emitter: bool = False,
    ) -> ToolExecutionDomain:
        """Determines the execution domain using step-down resolution rules."""
        resolvers = [
            lambda: self._domain_from_overrides(tool_name),
            lambda: self._domain_from_definitions(tool_name, ctx),
            lambda: self._domain_from_handlers(tool_name, ctx, has_local_handler),
            lambda: self._domain_from_memory(tool_name, is_memory_tool),
            lambda: self._domain_from_mcp(tool_name, has_mcp_client),
            lambda: self._domain_from_conventions(tool_name),
        ]
        for resolve in resolvers:
            resolved = resolve()
            if resolved is not None:
                return resolved
        return self._default_domain(has_pipe_emitter)

    def _domain_from_overrides(self, tool_name: str) -> Optional[ToolExecutionDomain]:
        return self.domain_overrides.get(tool_name)

    def _domain_from_definitions(
        self, tool_name: str, ctx: Optional[AgentContext]
    ) -> Optional[ToolExecutionDomain]:
        tool_def = self.tool_definitions.get(tool_name)
        if not tool_def and ctx and ctx.available_tools:
            tool_def = next((t for t in ctx.available_tools if t.name == tool_name), None)
        if tool_def and tool_def.execution_domain:
            return ToolExecutionDomain(tool_def.execution_domain)
        return None

    def _domain_from_handlers(
        self,
        tool_name: str,
        ctx: Optional[AgentContext],
        has_local_handler: bool,
    ) -> Optional[ToolExecutionDomain]:
        if has_local_handler:
            return ToolExecutionDomain.PYTHON_LOCAL
        if ctx and ctx.local_handlers and tool_name in ctx.local_handlers:
            return ToolExecutionDomain.PYTHON_LOCAL
        return None

    def _domain_from_memory(
        self, tool_name: str, is_memory_tool: bool
    ) -> Optional[ToolExecutionDomain]:
        if is_memory_tool or tool_name.startswith("memory_"):
            return ToolExecutionDomain.PYTHON_LOCAL
        return None

    def _domain_from_mcp(
        self, tool_name: str, has_mcp_client: bool
    ) -> Optional[ToolExecutionDomain]:
        if tool_name.startswith("mcp_"):
            return ToolExecutionDomain.MCP_BRIDGE
        if has_mcp_client and tool_name.startswith("browser_"):
            return ToolExecutionDomain.MCP_BRIDGE
        return None

    def _domain_from_conventions(self, tool_name: str) -> Optional[ToolExecutionDomain]:
        if any(tool_name.startswith(pfx) for pfx in GO_TOOL_PREFIXES):
            return ToolExecutionDomain.GO_NATIVE
        return None

    def _default_domain(self, has_pipe_emitter: bool) -> ToolExecutionDomain:
        if has_pipe_emitter:
            return ToolExecutionDomain.GO_NATIVE
        return ToolExecutionDomain.PYTHON_LOCAL
