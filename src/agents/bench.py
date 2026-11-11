"""Interactive and CLI Test Bench for Layer 6 Agents."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from typing import Any, AsyncIterator, Dict, List, Optional

from dotenv import load_dotenv

from src.agents.contracts import (
    AgentType,
    PipeEmitterProtocol,
    PipeReaderProtocol,
    ToolCallIntent,
    ToolCallResult,
)
from src.agents.factory import create_agent, create_all_agents
from src.models.base import BaseLLMClient
from src.models.types import StreamChunk, ToolCallChunk

# Automatically load environment variables
load_dotenv("config/.env")
load_dotenv(".env")


class Color:
    GREY = "\033[90m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class ConsolePipeEmitter(PipeEmitterProtocol):
    """Streams thoughts, tokens, and tool invocations live to the console."""

    async def emit_thought(self, turn_id: str, agent_name: str, thought: str) -> None:
        print(f"{Color.GREY}[{agent_name} Thought]: {thought}{Color.RESET}")

    async def emit_token(self, turn_id: str, agent_name: str, token: str) -> None:
        sys.stdout.write(token)
        sys.stdout.flush()

    async def emit_tool_call(self, turn_id: str, intent: ToolCallIntent) -> None:
        args_str = json.dumps(intent.arguments)
        print(f"\n{Color.CYAN}>>> [{intent.tool_name}]: {args_str}{Color.RESET}")

    async def emit_status(self, turn_id: str, agent_name: str, status_msg: str) -> None:
        print(f"{Color.YELLOW}[{agent_name} Status]: {status_msg}{Color.RESET}")


class LiveGoToolBridgeReader(PipeReaderProtocol):
    """Executes remote tool calls natively via the Go Layer 3 Tool Engine."""

    def __init__(self, mock_tools: bool = False) -> None:
        self.mock_tools = mock_tools
        self.pending_intents: List[ToolCallIntent] = []

    def queue_intent(self, intent: ToolCallIntent) -> None:
        self.pending_intents.append(intent)

    async def wait_for_tool_results(self, turn_id: str, expected_count: int) -> List[ToolCallResult]:
        intents = self.pending_intents[:expected_count]
        self.pending_intents = self.pending_intents[expected_count:]

        results: List[ToolCallResult] = []
        for intent in intents:
            if self.mock_tools:
                results.append(ToolCallResult(call_id=intent.call_id, output=f"Simulated output for {intent.tool_name}"))
            else:
                result = await asyncio.to_thread(self._run_native_tool, intent)
                results.append(result)
        return results

    def _run_native_tool(self, intent: ToolCallIntent) -> ToolCallResult:
        try:
            proc = subprocess.run(
                ["go", "run", "./cmd/bench/tools", "-tool", intent.tool_name, "-args", json.dumps(intent.arguments)],
                capture_output=True,
                text=True,
                timeout=35,
            )
            stdout = proc.stdout
            if "[STDOUT]" in stdout:
                parts = stdout.split("[STDOUT]\n", 1)[1]
                content = parts.split("\n============================================================", 1)[0]
                return ToolCallResult(call_id=intent.call_id, output=content.strip(), is_error=False)
            elif "[STDERR]" in stdout:
                parts = stdout.split("[STDERR]\n", 1)[1]
                content = parts.split("\n============================================================", 1)[0]
                return ToolCallResult(call_id=intent.call_id, output=content.strip(), is_error=True)
            return ToolCallResult(call_id=intent.call_id, output=stdout.strip(), is_error=proc.returncode != 0)
        except Exception as exc:
            return ToolCallResult(call_id=intent.call_id, output=f"Execution error: {exc}", is_error=True)


class LiveEmitterWithBridge(ConsolePipeEmitter):
    def __init__(self, bridge: LiveGoToolBridgeReader) -> None:
        self.bridge = bridge

    async def emit_tool_call(self, turn_id: str, intent: ToolCallIntent) -> None:
        await super().emit_tool_call(turn_id, intent)
        self.bridge.queue_intent(intent)


class MockBenchLLMClient(BaseLLMClient):
    """Deterministic mock client for offline verification."""

    def __init__(self) -> None:
        super().__init__(model_name="mock-bench-llm")

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[StreamChunk]:
        last_message = messages[-1].get("content", "")
        yield StreamChunk(thought="Evaluating task in offline mode...")

        if any(msg.get("role") == "tool" for msg in messages):
            yield StreamChunk(text_delta="Tool execution completed successfully.")
            return

        if tools and ("git" in last_message.lower() or "branch" in last_message.lower()):
            yield StreamChunk(
                tool_calls=[
                    ToolCallChunk(
                        call_id="call_mock_1",
                        tool_name="git_status",
                        arguments_json='{"repo_path": "."}',
                    )
                ]
            )
        elif tools and "file" in last_message.lower():
            yield StreamChunk(
                tool_calls=[
                    ToolCallChunk(
                        call_id="call_mock_2",
                        tool_name="fs_read",
                        arguments_json='{"path": "go.mod", "start_line": 1, "end_line": 5}',
                    )
                ]
            )
        else:
            yield StreamChunk(text_delta=f"Response for: {last_message}")


async def execute_agent_prompt(
    agent_type: AgentType,
    prompt: str,
    history: List[Dict[str, Any]],
    model_client: Optional[BaseLLMClient],
    mock_tools: bool,
    turn_counter: int,
) -> tuple[str, int]:
    bridge = LiveGoToolBridgeReader(mock_tools=mock_tools)
    emitter = LiveEmitterWithBridge(bridge)

    turn_id = f"turn_{turn_counter:03d}"

    if agent_type == AgentType.MANAGER:
        from src.orchestrator.manager.manager import ManagerAgent
        manager = ManagerAgent()
        plan_dict = await manager.plan(goal=prompt, conversation_history=history)
        return json.dumps(plan_dict, indent=2), 1
    else:
        worker = create_agent(agent_type=agent_type, model_client=model_client)
        result = await worker.execute_turn(
            session_id="manual_bench_session",
            turn_id=turn_id,
            prompt=prompt,
            history=history,
            pipe_emitter=emitter,
            pipe_reader=bridge,
        )
        return result.final_response, result.iterations_used


async def interactive_repl(agent_type: AgentType, model_client: Optional[BaseLLMClient], mock_tools: bool) -> None:
    print(f"\n{Color.BOLD}{Color.GREEN}=== Interactive REPL Session: @{agent_type.value} ==={Color.RESET}")
    print("Type your message and press Enter. Type 'exit' or 'quit' to end.\n")

    history: List[Dict[str, Any]] = []
    turn_counter = 1

    while True:
        try:
            prompt = input(f"{Color.BOLD}@{agent_type.value} > {Color.RESET}").strip()
            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit", "q"):
                print("Exiting session.")
                break

            response, _ = await execute_agent_prompt(
                agent_type=agent_type,
                prompt=prompt,
                history=history,
                model_client=model_client,
                mock_tools=mock_tools,
                turn_counter=turn_counter,
            )

            print(f"\n{Color.BOLD}Response:{Color.RESET}\n{response}\n")

            history.append({"role": "user", "content": prompt})
            history.append({"role": "assistant", "content": response})
            turn_counter += 1

        except (KeyboardInterrupt, EOFError):
            print("\nExiting session.")
            break


async def main() -> None:
    parser = argparse.ArgumentParser(description="Layer 6 Agent Engine Manual Test Bench")
    parser.add_argument(
        "--agent",
        choices=["manager", "system", "research", "browser", "productivity"],
        default="system",
        help="Agent persona to test (default: system)",
    )
    parser.add_argument("--prompt", help="Single prompt to execute (omit for interactive REPL)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive multi-turn REPL")
    parser.add_argument("--mock-llm", action="store_true", help="Force offline mock LLM client")
    parser.add_argument("--mock-tools", action="store_true", help="Simulate tool results instead of running native Go tools")
    args = parser.parse_args()

    agent_type = AgentType(args.agent)

    model_client: Optional[BaseLLMClient] = None
    if args.mock_llm:
        print(f"{Color.YELLOW}Notice: Using offline MockBenchLLMClient{Color.RESET}")
        model_client = MockBenchLLMClient()
    elif not os.getenv("GEMINI_API_KEY"):
        print(f"{Color.YELLOW}Notice: GEMINI_API_KEY not detected. Using MockBenchLLMClient{Color.RESET}")
        model_client = MockBenchLLMClient()

    if args.interactive or not args.prompt:
        await interactive_repl(agent_type, model_client, args.mock_tools)
    else:
        print("=" * 60)
        print(f"Testing Agent: @{agent_type.value}")
        print(f"Prompt:        {args.prompt}")
        print("=" * 60)

        response, iterations = await execute_agent_prompt(
            agent_type=agent_type,
            prompt=args.prompt,
            history=[],
            model_client=model_client,
            mock_tools=args.mock_tools,
            turn_counter=1,
        )

        print("\n" + "=" * 60)
        print(f"Iterations Used: {iterations}")
        print(f"{Color.BOLD}Final Response:{Color.RESET}\n{response}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
