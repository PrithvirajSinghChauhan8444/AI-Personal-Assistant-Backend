"""Playwright MCP Bridge for Layer 6 BrowserAgent.

Connects the Python Cognitive Layer to an isolated Playwright MCP Server
spawning the user-configured browser (e.g. Brave) over stdio JSON-RPC.
"""

import asyncio
import json
import logging
import os
import subprocess
from typing import Any, Dict, List, Optional

from src.agents.contracts import PipeReaderProtocol, ToolCallIntent, ToolCallResult

logger = logging.getLogger(__name__)


class PlaywrightMCPBridge(PipeReaderProtocol):
    """Bridges ReAct tool calls directly to a running Playwright MCP server."""

    def __init__(
        self,
        executable_path: Optional[str] = None,
        user_data_dir: Optional[str] = None,
        viewport_size: str = "1280x720",
        isolated: bool = True,
        headless: bool = False,
    ) -> None:
        self.executable_path = executable_path or os.getenv("BROWSER_EXECUTABLE_PATH", "/usr/bin/brave")
        self.user_data_dir = user_data_dir or os.getenv("BROWSER_USER_DATA_DIR", "")
        self.viewport_size = viewport_size
        self.isolated = isolated
        self.headless = headless

        self._proc: Optional[subprocess.Popen] = None
        self._req_id = 0
        self._pending_intents: List[ToolCallIntent] = []
        self._lock = asyncio.Lock()

    def start(self) -> None:
        """Launches the Playwright MCP server process with configured flags."""
        if self._proc is not None:
            return

        cmd = ["npx", "-y", "@playwright/mcp@latest"]

        if self.executable_path:
            cmd.append(f"--executable-path={os.path.expanduser(self.executable_path)}")

        if self.isolated:
            cmd.append("--isolated")
        elif self.user_data_dir:
            cmd.append(f"--user-data-dir={os.path.expanduser(self.user_data_dir)}")

        if self.viewport_size:
            cmd.append(f"--viewport-size={self.viewport_size}")

        if self.headless:
            cmd.append("--headless")

        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        # Step 1: Initialize
        self._send_rpc({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "browser-agent-bridge", "version": "1.0.0"},
            },
        })
        init_res = self._recv_rpc()
        if "error" in init_res:
            raise RuntimeError(f"Playwright MCP initialization failed: {init_res['error']}")

        # Step 2: Notify initialized
        self._send_rpc({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })

    def stop(self) -> None:
        """Shuts down the Playwright MCP server subprocess."""
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            finally:
                self._proc = None

    def queue_intent(self, intent: ToolCallIntent) -> None:
        """Enqueues an incoming tool intent from the ReAct engine."""
        self._pending_intents.append(intent)

    async def wait_for_tool_results(self, turn_id: str, expected_count: int) -> List[ToolCallResult]:
        """Processes enqueued browser intents and returns ToolCallResults."""
        intents = self._pending_intents[:expected_count]
        self._pending_intents = self._pending_intents[expected_count:]

        results: List[ToolCallResult] = []
        for intent in intents:
            res = await self.execute_tool(intent.tool_name, intent.arguments, intent.call_id)
            results.append(res)
        return results

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], call_id: str = "") -> ToolCallResult:
        """Executes a single tool via Playwright MCP JSON-RPC."""
        async with self._lock:
            if self._proc is None:
                self.start()

            # Normalize tool names & parameters to Playwright MCP format
            mapped_name = tool_name
            mapped_args = dict(arguments)

            if tool_name == "browser_read_content":
                mapped_name = "browser_snapshot"
                mapped_args = {}
            elif tool_name == "browser_screenshot":
                mapped_name = "browser_take_screenshot"
            elif tool_name == "browser_type":
                if "selector" in mapped_args and "target" not in mapped_args:
                    mapped_args["target"] = mapped_args.pop("selector")
            elif tool_name == "browser_click":
                if "selector" in mapped_args and "target" not in mapped_args:
                    mapped_args["target"] = mapped_args.pop("selector")

            req_id = self._next_id()
            rpc_req = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": "tools/call",
                "params": {
                    "name": mapped_name,
                    "arguments": mapped_args,
                },
            }

            try:
                await asyncio.to_thread(self._send_rpc, rpc_req)
                resp = await asyncio.to_thread(self._recv_rpc)

                if "error" in resp:
                    err_msg = resp["error"].get("message", "Unknown MCP error")
                    return ToolCallResult(call_id=call_id, output=f"MCP Error: {err_msg}", is_error=True)

                result_data = resp.get("result", {})
                is_error = result_data.get("isError", False)
                content_blocks = result_data.get("content", [])

                texts = []
                for block in content_blocks:
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))

                output_str = "\n".join(texts) if texts else "Action completed successfully."
                return ToolCallResult(call_id=call_id, output=output_str, is_error=is_error)

            except Exception as exc:
                return ToolCallResult(call_id=call_id, output=f"Failed to execute tool {tool_name}: {exc}", is_error=True)

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _send_rpc(self, msg: Dict[str, Any]) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("Playwright MCP process is not running")
        line = json.dumps(msg) + "\n"
        self._proc.stdin.write(line)
        self._proc.stdin.flush()

    def _recv_rpc(self) -> Dict[str, Any]:
        if self._proc is None or self._proc.stdout is None:
            raise RuntimeError("Playwright MCP process is not running")
        line = self._proc.stdout.readline()
        if not line:
            return {"error": {"message": "EOF from Playwright MCP process"}}
        return json.loads(line)
