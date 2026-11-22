"""SystemAgent implementation."""

import subprocess
from typing import Any, Dict, List, Optional

from src.agents.contracts import (
    AgentContext,
    AgentTurnResult,
    AgentType,
    MemoryEngineProtocol,
    PipeEmitterProtocol,
    PipeReaderProtocol,
)
from src.agents.engine.react_engine import run_worker_agent
from src.agents.system.prompts import get_system_prompt
from src.agents.system.tools import SYSTEM_TOOLS
from src.models.base import BaseLLMClient


class SystemAgent:
    """Specialized worker for Linux OS, shell execution, filesystem, and Git."""

    def __init__(self, model_client: BaseLLMClient) -> None:
        self.model_client = model_client
        self.agent_type = AgentType.SYSTEM
        self.system_prompt = get_system_prompt()
        self.tools = SYSTEM_TOOLS

    async def execute_turn(
        self,
        session_id: str,
        turn_id: str,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        pipe_emitter: Optional[PipeEmitterProtocol] = None,
        pipe_reader: Optional[PipeReaderProtocol] = None,
        memory_engine: Optional[MemoryEngineProtocol] = None,
        max_iterations: int = 10,
    ) -> AgentTurnResult:
        """Runs an autonomous execution turn for the system worker with request-specific session context."""
        request_context = _build_request_context(history)
        effective_prompt = f"{self.system_prompt}\n\n{request_context}" if request_context else self.system_prompt

        ctx = AgentContext(
            session_id=session_id,
            turn_id=turn_id,
            agent_type=self.agent_type,
            user_prompt=prompt,
            system_prompt=effective_prompt,
            conversation_history=history or [],
            available_tools=self.tools,
            max_iterations=max_iterations,
        )

        return await run_worker_agent(
            ctx=ctx,
            model_client=self.model_client,
            memory_engine=memory_engine,
            pipe_emitter=pipe_emitter,
            pipe_reader=pipe_reader,
        )


def _get_active_terminal_sessions() -> List[Dict[str, Any]]:
    """Discovers active persistent terminal sessions directly from tmux."""
    try:
        res = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}\t#{session_attached}\t#{session_windows}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode != 0:
            return []

        sessions = []
        for line in res.stdout.strip().splitlines():
            parts = line.split("\t")
            if parts and parts[0].strip():
                sessions.append({
                    "name": parts[0].strip(),
                    "attached": len(parts) > 1 and parts[1].strip() == "1",
                    "windows": int(parts[2].strip()) if len(parts) > 2 and parts[2].strip().isdigit() else 1,
                })
        return sessions
    except Exception:
        return []


def _extract_recent_terminal_context(history: Optional[List[Dict[str, Any]]]) -> List[str]:
    """Extracts terminal-related context and session mentions from recent conversation turns."""
    if not history:
        return []

    extracted: List[str] = []
    for msg in history[-6:]:
        role = msg.get("role", "unknown")
        content = str(msg.get("content", "")).strip()
        if not content:
            continue

        lower = content.lower()
        if any(keyword in lower for keyword in ["session", "terminal", "ssh", "tmux"]):
            summary = content if len(content) <= 180 else content[:177] + "..."
            extracted.append(f"[{role}]: {summary}")
    return extracted


def _build_request_context(history: Optional[List[Dict[str, Any]]]) -> str:
    """Builds dynamic, request-specific context on active terminal sessions and turn history."""
    sessions = _get_active_terminal_sessions()
    recent_turns = _extract_recent_terminal_context(history)

    parts: List[str] = []
    if sessions:
        session_lines = [
            f"- `{s['name']}` ({'attached to visible desktop window' if s['attached'] else 'background session'})"
            for s in sessions
        ]
        parts.append(
            "### Live Active Terminal Sessions on Host:\n"
            + "\n".join(session_lines)
            + "\n\n**CRITICAL SESSION REUSE RULE**: Active terminal sessions are already open on the host. "
            "If this request continues previous work, relates to an established remote connection, or requires terminal interaction, "
            "you MUST PREFER using an existing session via tmux-mcp tools (`tmux__execute-command`, `tmux__capture-pane`) "
            "instead of spawning duplicate connections or new subprocesses via `sys_exec`."
        )

    if recent_turns:
        parts.append(
            "### Recent Terminal / Interactive Turns Context:\n"
            + "\n".join(recent_turns)
        )

    return "\n\n".join(parts)
