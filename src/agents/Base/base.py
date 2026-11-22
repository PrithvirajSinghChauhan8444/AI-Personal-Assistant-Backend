"""Standard Base Agent coordinating modular subsystems in src.agents.Base."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from src.agents.Base.AgentHooks import AgentHooks
from src.agents.Base.AgentValidator import AgentValidator, infer_agent_name
from src.agents.Base.ContextBuilder import ContextBuilder
from src.agents.Base.PromptManager import PromptManager
from src.agents.Base.ToolRegistry import ToolRegistry
from src.agents.contracts import (
    AgentContext,
    AgentTurnResult,
    AgentType,
    MemoryEngineProtocol,
    PipeEmitterProtocol,
    PipeReaderProtocol,
    ToolCallIntent,
    ToolCallResult,
    ToolDefinition,
)
from src.agents.engine.react_engine import run_worker_agent
from src.agents.engine.tool_dispatcher import ToolDispatcher, ToolTurnExecutionResult
from src.agents.manifest import AgentManifest, find_agent_config, load_manifest
from src.models.base import BaseLLMClient


class BaseAgent:
    """Standard base class for Layer 6 Specialist Worker Agents."""

    agent_type: Optional[Union[AgentType, str]] = None

    def __init__(
        self,
        model_client: BaseLLMClient,
        agent_type: Optional[Union[AgentType, str]] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[Sequence[ToolDefinition]] = None,
        manifest_path: Optional[Union[str, Path]] = None,
        manifest: Optional[AgentManifest] = None,
        memory_engine: Optional[MemoryEngineProtocol] = None,
        max_iterations: int = 10,
        metadata: Optional[Dict[str, Any]] = None,
        local_handlers: Optional[Dict[str, Any]] = None,
        tool_dispatcher: Optional[ToolDispatcher] = None,
        **kwargs: Any,
    ) -> None:
        if model_client is None:
            raise ValueError("model_client must not be None")

        self._model_client = model_client
        self.model_client = model_client
        self._memory_engine = memory_engine
        self._max_iterations = max(1, max_iterations)
        self._metadata = dict(metadata or {})
        self.tool_dispatcher = tool_dispatcher

        # 1. Identity Resolution
        raw_type = agent_type or getattr(self.__class__, "agent_type", None) or infer_agent_name(self.__class__.__name__)
        if isinstance(raw_type, str):
            try:
                self.agent_type = AgentType(raw_type.lower())
            except ValueError:
                self.agent_type = raw_type
        else:
            self.agent_type = raw_type

        self.agent_name = str(
            self.agent_type.value if hasattr(self.agent_type, "value") else self.agent_type
        ).lower().strip()

        # 2. Manifest Resolution (Convention-over-Configuration)
        self.manifest: Optional[AgentManifest] = manifest or self._resolve_manifest(manifest_path)
        if self.manifest and self.manifest.agent_identifier:
            if not agent_type and getattr(self.__class__, "agent_type", None) is None:
                manifest_id = self.manifest.agent_identifier.lower()
                try:
                    self.agent_type = AgentType(manifest_id)
                except ValueError:
                    self.agent_type = manifest_id
                self.agent_name = manifest_id

        # 3. Prompt Resolution
        resolved_prompt = system_prompt
        if not resolved_prompt:
            cls_prompt = getattr(self.__class__, "system_prompt", None)
            if cls_prompt is not None and not isinstance(cls_prompt, property) and isinstance(cls_prompt, str):
                resolved_prompt = cls_prompt

        self.prompts = PromptManager(
            initial_prompt=resolved_prompt,
            owner_class=self.__class__,
            agent_name=self.agent_name,
        )

        # 4. Explicit Tool Resolution ("A tool exists to be used" - No auto-discovery)
        resolved_tools = tools
        if resolved_tools is None:
            cls_tools = getattr(self.__class__, "tools", None)
            if cls_tools is not None and not isinstance(cls_tools, property) and isinstance(cls_tools, (list, tuple)):
                resolved_tools = cls_tools

        self.registry = ToolRegistry(resolved_tools or [])

        # 5. Local Execution Handlers
        existing_handlers = getattr(self, "local_handlers", None)
        if local_handlers is not None:
            self.local_handlers = dict(local_handlers)
        elif existing_handlers is not None and isinstance(existing_handlers, dict) and len(existing_handlers) > 0:
            self.local_handlers = dict(existing_handlers)
        else:
            cls_handlers = getattr(self.__class__, "local_handlers", None)
            if cls_handlers is not None and not isinstance(cls_handlers, property) and isinstance(cls_handlers, dict):
                self.local_handlers = dict(cls_handlers)
            else:
                self.local_handlers = {}

        # 6. Polyglot ToolDispatcher Setup
        if tool_dispatcher is not None:
            self.tool_dispatcher = tool_dispatcher
            for tool in self.get_tools():
                self.tool_dispatcher.register_tool_definition(tool)
            for name, handler in self.local_handlers.items():
                self.tool_dispatcher.register_handler(name, handler)
        else:
            self.tool_dispatcher = ToolDispatcher(
                tools=self.get_tools(),
                local_handlers=self.local_handlers,
                memory_engine=self._memory_engine,
            )

        # 7. Lifecycle Hooks
        self.lifecycle = AgentHooks(self.agent_name)

        # Backward-compatibility aliases
        self._prompt_manager = self.prompts
        self._tool_registry = self.registry

    def _resolve_manifest(self, manifest_path: Optional[Union[str, Path]]) -> Optional[AgentManifest]:
        """Resolves agent manifest from explicit path or directory convention."""
        if manifest_path:
            return load_manifest(manifest_path)

        module_name = getattr(self.__class__, "__module__", "")
        cls_module = sys.modules.get(module_name)
        if cls_module and hasattr(cls_module, "__file__") and cls_module.__file__:
            agent_dir = Path(cls_module.__file__).resolve().parent
            cfg_path = find_agent_config(agent_dir, self.agent_name)
            if cfg_path:
                return load_manifest(cfg_path)
        return None

    async def execute_turn(
        self,
        session_id: str,
        turn_id: str,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        pipe_emitter: Optional[PipeEmitterProtocol] = None,
        pipe_reader: Optional[PipeReaderProtocol] = None,
        memory_engine: Optional[MemoryEngineProtocol] = None,
        max_iterations: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tool_dispatcher: Optional[ToolDispatcher] = None,
    ) -> AgentTurnResult:
        """Executes an autonomous turn delegating to the ReAct engine."""
        ctx = self.create_context(session_id, turn_id, prompt, history, max_iterations, metadata)
        self.before_turn(ctx)
        try:
            result = await run_worker_agent(
                ctx=ctx,
                model_client=self._model_client,
                memory_engine=memory_engine or self._memory_engine,
                pipe_emitter=pipe_emitter,
                pipe_reader=pipe_reader,
                tool_dispatcher=tool_dispatcher or getattr(self, "tool_dispatcher", None),
            )
            return self.after_turn(result, ctx)
        except Exception as exc:
            return self.on_turn_error(exc, ctx)

    # Lifecycle Hooks
    def before_turn(self, ctx: AgentContext) -> None:
        self.lifecycle.before_turn(ctx)

    def after_turn(self, result: AgentTurnResult, ctx: AgentContext) -> AgentTurnResult:
        return self.lifecycle.after_turn(result, ctx)

    def on_turn_error(self, error: Exception, ctx: AgentContext) -> AgentTurnResult:
        return self.lifecycle.on_turn_error(error, ctx)

    # Context Construction
    def create_context(
        self,
        session_id: str,
        turn_id: str,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        max_iterations: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentContext:
        local_handlers = getattr(self, "local_handlers", {})
        return ContextBuilder.build(
            session_id=session_id,
            turn_id=turn_id,
            prompt=prompt,
            agent_type=self.agent_type,
            system_prompt=self.get_system_prompt(),
            tools=self.get_tools(),
            history=history,
            max_iterations=max_iterations or self._max_iterations,
            base_metadata=self._metadata,
            override_metadata=metadata,
            local_handlers=local_handlers,
        )

    # Validation & Diagnostics (Delegates to subsystems)
    def validate(self) -> None:
        """Runs validation checks defined across the related subsystem files."""
        AgentValidator.validate_agent(self)

    def describe(self) -> Dict[str, Any]:
        """Emits structured telemetry describing the agent, its tools, and manifest."""
        return AgentValidator.describe(
            self.agent_name,
            self.agent_type,
            self._model_client,
            self.get_tools(),
            self._max_iterations,
            manifest=self.manifest,
        )

    # Prompt Accessors
    @property
    def system_prompt(self) -> str:
        return self.prompts.get_prompt()

    @system_prompt.setter
    def system_prompt(self, new_prompt: str) -> None:
        self.prompts.set_prompt(new_prompt)

    def get_system_prompt(self) -> str:
        return self.prompts.get_prompt()

    def set_system_prompt(self, prompt: str) -> None:
        self.prompts.set_prompt(prompt)

    def format_system_prompt(self, **kwargs: Any) -> str:
        return self.prompts.format_prompt(**kwargs)

    @staticmethod
    def load_prompt_from_file(prompt_path: Union[str, Path], fallback: str = "") -> str:
        return PromptManager.load_from_file(prompt_path, fallback)

    # Tool Accessors
    @property
    def tools(self) -> List[ToolDefinition]:
        return self.registry.all()

    @tools.setter
    def tools(self, new_tools: Sequence[ToolDefinition]) -> None:
        self.registry.clear()
        self.registry.register_all(new_tools)
        if getattr(self, "tool_dispatcher", None) is not None:
            for tool in new_tools:
                self.tool_dispatcher.register_tool_definition(tool)

    def get_tools(self) -> List[ToolDefinition]:
        return self.registry.all()

    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        return self.registry.get(tool_name)

    def has(self, tool_name: str) -> bool:
        return self.registry.has(tool_name)

    def has_tool(self, tool_name: str) -> bool:
        return self.registry.has(tool_name)

    def register_tool(self, tool: ToolDefinition) -> None:
        self.registry.register(tool)
        if getattr(self, "tool_dispatcher", None) is not None:
            self.tool_dispatcher.register_tool_definition(tool)

    def register_tools(self, tools: Sequence[ToolDefinition]) -> None:
        self.registry.register_all(tools)
        if getattr(self, "tool_dispatcher", None) is not None:
            for tool in tools:
                self.tool_dispatcher.register_tool_definition(tool)

    def unregister_tool(self, tool_name: str) -> bool:
        res = self.registry.unregister(tool_name)
        if getattr(self, "tool_dispatcher", None) is not None:
            self.tool_dispatcher.unregister_tool(tool_name)
        return res

    def clear_tools(self) -> None:
        self.registry.clear()
        if getattr(self, "tool_dispatcher", None) is not None:
            for tool_name in list(self.tool_dispatcher.get_registered_tools().keys()):
                self.tool_dispatcher.unregister_tool(tool_name)

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        call_id: Optional[str] = None,
        ctx: Optional[AgentContext] = None,
    ) -> ToolCallResult:
        """Directly invokes a single tool via the agent's ToolDispatcher."""
        intent = ToolCallIntent(
            call_id=call_id or f"call_{tool_name}",
            tool_name=tool_name,
            arguments=arguments,
        )
        return await self.tool_dispatcher.execute_intent(intent, ctx)

    async def execute_turn_response(
        self,
        response: Any,
        ctx: Optional[AgentContext] = None,
        turn_id: Optional[str] = None,
    ) -> ToolTurnExecutionResult:
        """Parses and executes all tool calls in an LLM turn response via ToolDispatcher."""
        return await self.tool_dispatcher.execute_turn_response(response, ctx=ctx, turn_id=turn_id)

    def filter_by_risk(self, max_risk: str = "HIGH") -> List[ToolDefinition]:
        return self.registry.filter_by_risk(max_risk)

    def filter_tools_by_risk(self, max_risk: str = "HIGH") -> List[ToolDefinition]:
        return self.registry.filter_by_risk(max_risk)

    def to_tool_schemas(self) -> List[Dict[str, Any]]:
        return self.registry.to_schemas()

    def __repr__(self) -> str:
        model = getattr(self._model_client, "model_name", "custom")
        return f"<{self.__class__.__name__} name='{self.agent_name}' tools={len(self.registry)} model='{model}'>"
