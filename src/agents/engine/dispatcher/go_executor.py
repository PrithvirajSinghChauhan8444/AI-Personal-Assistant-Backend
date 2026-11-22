"""Go native tool executor via Layer 4 IPC Bridge or standalone subprocess."""

from __future__ import annotations

import asyncio
import json
import subprocess
from typing import Optional

from src.agents.contracts import (
    AgentContext,
    PipeEmitterProtocol,
    PipeReaderProtocol,
    ToolCallIntent,
    ToolCallResult,
)


class GoToolExecutor:
    """Dispatches Go native tool executions via IPC pipe or standalone runner."""

    def __init__(
        self,
        pipe_emitter: Optional[PipeEmitterProtocol] = None,
        pipe_reader: Optional[PipeReaderProtocol] = None,
        subprocess_fallback: bool = False,
    ) -> None:
        self.pipe_emitter = pipe_emitter
        self.pipe_reader = pipe_reader
        self.subprocess_fallback = subprocess_fallback

    @property
    def has_ipc(self) -> bool:
        """Indicates whether Layer 4 IPC pipes are connected."""
        return self.pipe_emitter is not None and self.pipe_reader is not None

    async def execute(
        self, intent: ToolCallIntent, ctx: Optional[AgentContext] = None
    ) -> ToolCallResult:
        """Executes a Go native tool via IPC or local subprocess fallback."""
        if self.has_ipc:
            turn_id = ctx.turn_id if ctx else "default_turn"
            return await self._execute_ipc(intent, turn_id)
        if self.subprocess_fallback:
            return await asyncio.to_thread(self._execute_subprocess, intent)
        return self._simulate(intent)

    async def _execute_ipc(self, intent: ToolCallIntent, turn_id: str) -> ToolCallResult:
        await self.pipe_emitter.emit_tool_call(turn_id, intent)  # type: ignore[union-attr]
        results = await self.pipe_reader.wait_for_tool_results(turn_id, 1)  # type: ignore[union-attr]
        if results:
            return results[0]
        return ToolCallResult(
            call_id=intent.call_id,
            output=f"Timeout waiting for IPC result for '{intent.tool_name}'",
            is_error=True,
        )

    def _execute_subprocess(self, intent: ToolCallIntent) -> ToolCallResult:
        try:
            args_json = json.dumps(intent.arguments)
            cmd = ["go", "run", "./cmd/bench/tools", "-tool", intent.tool_name, "-args", args_json]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                err = proc.stderr.strip() or f"exit code {proc.returncode}"
                return ToolCallResult(call_id=intent.call_id, output=f"Go error: {err}", is_error=True)
            return ToolCallResult(call_id=intent.call_id, output=proc.stdout.strip(), is_error=False)
        except Exception as exc:
            return ToolCallResult(
                call_id=intent.call_id,
                output=f"Go subprocess error for '{intent.tool_name}': {exc}",
                is_error=True,
            )

    def _simulate(self, intent: ToolCallIntent) -> ToolCallResult:
        return ToolCallResult(
            call_id=intent.call_id,
            output=f"Simulated Go tool execution for '{intent.tool_name}': {intent.arguments}",
            is_error=False,
        )
