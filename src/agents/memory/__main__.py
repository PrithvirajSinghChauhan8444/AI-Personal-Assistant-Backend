"""Standalone executable CLI entrypoint for Memory Worker Agent."""

import asyncio
from datetime import datetime
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from src.agents.contracts import (
    PipeEmitterProtocol,
    PipeReaderProtocol,
    ToolCallIntent,
    ToolCallResult,
)
from src.agents.factory import load_agents_config
from src.agents.memory.agent import MemoryAgent
from src.models.factory import ModelFactory

load_dotenv("config/.env")
load_dotenv(".env")


class StandaloneConsoleEmitter(PipeEmitterProtocol, PipeReaderProtocol):
    """Local I/O pipe emitter matching Layer 1 CLI StreamRenderer style."""

    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.has_streamed_tokens = False
        self._in_token_stream = False
        self._last_was_newline = True

    def _ensure_clean_line(self) -> None:
        if self._in_token_stream:
            if not self._last_was_newline:
                sys.stdout.write("\n")
                self._last_was_newline = True
            self._in_token_stream = False

    async def emit_thought(self, turn_id: str, agent_name: str, thought: str) -> None:
        if self.verbose and thought.strip():
            self._ensure_clean_line()
            sys.stdout.write(f"\033[90m💭 [{agent_name} thought] {thought.strip()}\033[0m\n")
            sys.stdout.flush()
            self._last_was_newline = True

    async def emit_token(self, turn_id: str, agent_name: str, token: str) -> None:
        if not self._in_token_stream:
            self._in_token_stream = True
            if not self._last_was_newline:
                sys.stdout.write("\n")
        self.has_streamed_tokens = True
        sys.stdout.write(token)
        sys.stdout.flush()
        self._last_was_newline = token.endswith("\n")

    async def emit_tool_call(self, turn_id: str, intent: ToolCallIntent) -> None:
        if not self.verbose:
            return
        self._ensure_clean_line()
        border = "\033[38;2;100;116;139m"  # Slate #64748B
        badge = "\033[1;36m[memory]\033[0m"
        tool_style = "\033[1;38;2;56;189;248m"  # Sky #38BDF8
        label_style = "\033[38;2;148;163;184m"  # Slate #94A3B8
        val_style = "\033[38;2;241;245;249m"  # Off-white #F1F5F9
        rst = "\033[0m"

        sys.stdout.write(f"{border}╭─{rst} 🛠  {badge} Tool Call: {tool_style}{intent.tool_name}{rst}\n")
        if intent.arguments:
            for k, v in intent.arguments.items():
                val_str = str(v)
                if len(val_str) > 120:
                    val_str = val_str[:117] + "..."
                sys.stdout.write(f"{border}│{rst}  {label_style}{k}:{rst} {val_style}{val_str}{rst}\n")
        sys.stdout.flush()
        self._last_was_newline = True

    async def emit_local_tool_call(self, turn_id: str, intent: ToolCallIntent) -> None:
        await self.emit_tool_call(turn_id, intent)

    async def emit_tool_result(
        self, turn_id: str, tool_name: str, output: str, duration_ms: int = 0, is_error: bool = False
    ) -> None:
        if not self.verbose:
            return
        self._ensure_clean_line()
        border = "\033[38;2;100;116;139m"
        rst = "\033[0m"
        meta_style = "\033[38;2;148;163;184m"
        out_style = "\033[38;2;203;213;225m"

        if is_error:
            glyph = "\033[1;31m✖\033[0m"
            status_text = f"\033[1;31m{tool_name} failed ({duration_ms}ms)\033[0m"
        else:
            glyph = "\033[1;32m✔\033[0m"
            status_text = f"\033[1;32m{tool_name} completed ({duration_ms}ms)\033[0m"

        sys.stdout.write(f"{border}╰─{rst} {glyph} {status_text}\n")
        if output:
            lines = output.strip().split("\n")
            if len(lines) == 1 and len(lines[0]) <= 120:
                sys.stdout.write(f"   {meta_style}Output:{rst} {out_style}{lines[0]}{rst}\n")
            else:
                sys.stdout.write(f"   {meta_style}Output ({len(lines)} lines):{rst}\n")
                for line in lines[:3]:
                    preview = line[:120] + "..." if len(line) > 120 else line
                    sys.stdout.write(f"   {border}│{rst} {out_style}{preview}{rst}\n")
                if len(lines) > 3:
                    sys.stdout.write(f"   {border}│{rst} {meta_style}... and {len(lines) - 3} more line(s){rst}\n")
        sys.stdout.write("\n")
        sys.stdout.flush()
        self._last_was_newline = True

    async def emit_local_tool_result(
        self, turn_id: str, tool_name: str, output: str, duration_ms: int = 0, is_error: bool = False
    ) -> None:
        await self.emit_tool_result(turn_id, tool_name, output, duration_ms, is_error)

    async def emit_status(self, turn_id: str, agent_name: str, status_msg: str) -> None:
        if self.verbose:
            self._ensure_clean_line()
            now_str = datetime.now().strftime("%H:%M:%S")
            sys.stdout.write(f"\033[33m●\033[0m \033[90m{now_str}\033[0m \033[1;36m[{agent_name}]\033[0m {status_msg}\n")
            sys.stdout.flush()
            self._last_was_newline = True

    def flush(self) -> None:
        self._ensure_clean_line()
        sys.stdout.flush()

    async def wait_for_tool_results(self, turn_id: str, expected_count: int) -> List[ToolCallResult]:
        return [
            ToolCallResult(
                call_id=f"standalone_sim_{idx}",
                output="Standalone CLI notice: Remote tool execution is not connected in standalone mode.",
                is_error=False,
            )
            for idx in range(expected_count)
        ]


async def main() -> None:
    """Runs the Memory Worker in standalone mode (single shot or interactive REPL)."""
    agents_cfg = load_agents_config()
    mem_cfg = agents_cfg.get("memory", {})
    model_name = mem_cfg.get("model", "google:gemini-3.5-flash-lite")
    temperature = float(mem_cfg.get("temperature", 0.0))

    model_client = ModelFactory.get_client(model_id=model_name, temperature=temperature)
    agent = MemoryAgent(model_client=model_client)

    args = sys.argv[1:]
    if args:
        prompt = " ".join(args)
        await agent.run_standalone(prompt)
        print()
        return

    # Interactive REPL mode
    print("============================================================")
    print("   🧠 Memory Worker Agent - Standalone Cognitive REPL")
    print("   Type your memory queries, rules to remember, or 'exit'.")
    print("============================================================\n")

    history: List[Dict[str, Any]] = []
    while True:
        try:
            user_input = input("\033[1;34mMemory> \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting Memory Worker shell.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Goodbye.")
            break

        print()
        result = await agent.run_standalone(prompt=user_input, history=history, verbose=True)
        print()

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": result.final_response})


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as exc:
        sys.stderr.write(f"\n[Memory Worker Fatal Error] {exc}\n")
        sys.exit(1)
