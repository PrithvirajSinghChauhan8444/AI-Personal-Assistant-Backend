"""Playwright MCP Bridge for Layer 6 BrowserAgent.

Connects the Python Cognitive Layer to an isolated or persistent Playwright MCP Server
spawning the user-configured browser (e.g. Brave, Chrome, Chromium) over stdio JSON-RPC.
"""

import asyncio
import json
import logging
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.agents.contracts import PipeReaderProtocol, ToolCallIntent, ToolCallResult

logger = logging.getLogger(__name__)


def try_load_dotenv() -> None:
    """Attempts to load .env key-value pairs if not already present in os.environ."""
    candidates = [".env", "config/.env", "../config/.env", "../../config/.env"]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, val = line.split("=", 1)
                            key = key.strip()
                            val = val.strip().strip("'\"")
                            if key not in os.environ:
                                os.environ[key] = val
                return
            except Exception:
                pass


def resolve_browser(browser_type: Optional[str] = None) -> Tuple[str, str]:
    """Resolves browser binary for brave, chrome, or chromium."""
    b_type = (browser_type or os.getenv("BROWSER_TYPE", "auto")).lower().strip()
    if not b_type:
        b_type = "auto"

    search_candidates = {
        "brave": [
            "brave",
            "brave-browser",
            "/usr/bin/brave",
            "/usr/bin/brave-browser",
            "/opt/brave.com/brave/brave-browser",
            "/snap/bin/brave",
        ],
        "chrome": [
            "google-chrome-stable",
            "google-chrome",
            "chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/opt/google/chrome/google-chrome",
        ],
        "chromium": [
            "chromium",
            "chromium-browser",
            "/usr/bin/chromium",
            "/usr/lib/chromium/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ],
    }

    def find_exe(candidates: List[str]) -> Optional[str]:
        for cand in candidates:
            if "/" in cand:
                if os.path.isfile(cand) and os.access(cand, os.X_OK):
                    return cand
            else:
                found = shutil.which(cand)
                if found:
                    return found
        return None

    if b_type == "brave":
        return "brave", find_exe(search_candidates["brave"]) or "/usr/bin/brave"
    if b_type in ("chrome", "google-chrome"):
        return "chrome", find_exe(search_candidates["chrome"]) or "/usr/bin/google-chrome"
    if b_type == "chromium":
        return "chromium", find_exe(search_candidates["chromium"]) or "/usr/bin/chromium"

    # auto mode: check in priority order
    for typ in ["brave", "chrome", "chromium"]:
        exe = find_exe(search_candidates[typ])
        if exe:
            return typ, exe

    return "chromium", "/usr/bin/chromium"


def resolve_user_data_dir(
    browser_type: str,
    profile_name: Optional[str] = None,
    explicit_dir: Optional[str] = None,
) -> str:
    """Computes the persistent profile directory path for the assistant."""
    if explicit_dir:
        return os.path.expanduser(explicit_dir)

    p_name = (profile_name or os.getenv("BROWSER_PROFILE_NAME", "assistant-profile")).strip()
    if not p_name:
        p_name = "assistant-profile"

    home = os.path.expanduser("~")
    folder_name = f"{browser_type}-{p_name}"
    return os.path.join(home, ".config", folder_name)


def is_cdp_open(cdp_url: str) -> bool:
    """Checks if CDP remote debugging port is open."""
    host = "127.0.0.1"
    port = 9222
    if "://" in cdp_url:
        parts = cdp_url.split("://", 1)[1].rstrip("/").split(":")
        host = parts[0]
        if len(parts) > 1:
            try:
                port = int(parts[1])
            except ValueError:
                port = 9222
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except (OSError, socket.timeout):
        return False


class PlaywrightMCPBridge(PipeReaderProtocol):
    """Bridges ReAct tool calls directly to a running Playwright MCP server."""

    def __init__(
        self,
        executable_path: Optional[str] = None,
        user_data_dir: Optional[str] = None,
        viewport_size: Optional[str] = None,
        isolated: Optional[bool] = None,
        headless: Optional[bool] = None,
        browser_type: Optional[str] = None,
        profile_name: Optional[str] = None,
    ) -> None:
        try_load_dotenv()

        resolved_type, auto_exe = resolve_browser(browser_type)
        self.browser_type = resolved_type
        self.executable_path = executable_path or os.getenv("BROWSER_EXECUTABLE_PATH") or auto_exe

        self.profile_name = profile_name or os.getenv("BROWSER_PROFILE_NAME", "assistant-profile")
        self.user_data_dir = resolve_user_data_dir(
            self.browser_type,
            self.profile_name,
            user_data_dir or os.getenv("BROWSER_USER_DATA_DIR"),
        )

        cfg_path = Path("src/agents/browser/browser_config.json")
        browser_cfg = {}
        if cfg_path.is_file():
            try:
                browser_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        self.viewport_size = viewport_size or os.getenv("BROWSER_VIEWPORT", "1280x720")

        if isolated is not None:
            self.isolated = isolated
        else:
            self.isolated = os.getenv("BROWSER_ISOLATED", "false").lower() == "true"

        if headless is not None:
            self.headless = headless
        elif "headless" in browser_cfg and os.getenv("BROWSER_HEADLESS") is None:
            self.headless = bool(browser_cfg["headless"])
        else:
            self.headless = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"

        self.attach_cdp = os.getenv("BROWSER_ATTACH_CDP", "false").lower() == "true"
        self.cdp_url = os.getenv("BROWSER_CDP_URL") or browser_cfg.get("cdp_url", "http://localhost:9222")
        self.slow_mo_ms = browser_cfg.get("slow_mo_ms", 1000)

        self._proc: Optional[subprocess.Popen] = None
        self._req_id = 0
        self._pending_intents: List[ToolCallIntent] = []
        self._lock = asyncio.Lock()

    def start(self) -> None:
        """Launches the Playwright MCP server process with configured flags."""
        if self._proc is not None:
            return

        cmd = ["npx", "-y", "@playwright/mcp@latest"]

        # CDP mode if user explicitly enabled it and port is active
        if self.attach_cdp and self.cdp_url and is_cdp_open(self.cdp_url):
            cmd.append(f"--cdp-endpoint={self.cdp_url}")
        else:
            if self.executable_path:
                cmd.append(f"--executable-path={os.path.expanduser(self.executable_path)}")

            if self.isolated:
                cmd.append("--isolated")
            elif self.user_data_dir:
                resolved_dir = os.path.expanduser(self.user_data_dir)
                os.makedirs(resolved_dir, exist_ok=True)
                cmd.append(f"--user-data-dir={resolved_dir}")

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
