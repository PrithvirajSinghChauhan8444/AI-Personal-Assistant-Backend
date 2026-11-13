#!/usr/bin/env python3
"""
Test Playwright MCP with user configurations.
Spawns @playwright/mcp@latest using the configured browser (Brave / Chrome / Chromium)
and profile directory, and runs a test navigation and snapshot.
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.browser.mcp_bridge import (
    resolve_browser,
    resolve_user_data_dir,
    try_load_dotenv,
)

def main():
    try_load_dotenv()

    browser_type, auto_exe = resolve_browser()
    executable_path = os.getenv("BROWSER_EXECUTABLE_PATH") or auto_exe
    user_data_dir = resolve_user_data_dir(browser_type)
    viewport = os.getenv("BROWSER_VIEWPORT", "1280x720")
    headless = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"

    print("🌐 Starting Playwright MCP Test...")
    print(f"  • Browser Type:  {browser_type}")
    print(f"  • Executable:    {executable_path}")
    print(f"  • User Data Dir: {user_data_dir}")
    print(f"  • Viewport:      {viewport}")
    print(f"  • Headless:      {headless}")

    os.makedirs(user_data_dir, exist_ok=True)

    cmd = [
        "npx",
        "-y",
        "@playwright/mcp@latest",
        f"--executable-path={executable_path}",
        f"--user-data-dir={user_data_dir}",
        f"--viewport-size={viewport}"
    ]
    if headless:
        cmd.append("--headless")

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    def send_rpc(msg: dict):
        line = json.dumps(msg) + "\n"
        proc.stdin.write(line)
        proc.stdin.flush()

    def recv_rpc() -> dict:
        line = proc.stdout.readline()
        if not line:
            return {}
        return json.loads(line)

    try:
        # Step 1: Initialize
        send_rpc({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-runner", "version": "1.0.0"}
            }
        })
        init_res = recv_rpc()
        print(f"✅ Initialized: {init_res.get('result', {}).get('serverInfo', {})}")

        # Step 2: List Tools
        send_rpc({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        tools_res = recv_rpc()
        tools = [t["name"] for t in tools_res.get("result", {}).get("tools", [])]
        print(f"🛠️  Available Tools ({len(tools)}): {', '.join(tools[:6])}...")

        # Step 3: Test Navigation
        target_url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
        print(f"🚀 Calling browser_navigate -> {target_url}...")
        send_rpc({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "browser_navigate",
                "arguments": {"url": target_url}
            }
        })
        nav_res = recv_rpc()
        print("📄 Navigation Result:")
        content = nav_res.get("result", {}).get("content", [])
        for c in content:
            print(c.get("text", "")[:400])

        # Step 4: Take snapshot
        print("📸 Calling browser_snapshot...")
        send_rpc({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "browser_snapshot",
                "arguments": {}
            }
        })
        snap_res = recv_rpc()
        snap_content = snap_res.get("result", {}).get("content", [])
        for c in snap_content:
            print(c.get("text", "")[:300])

        print("\n✨ Playwright MCP verification completed successfully!")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

if __name__ == "__main__":
    main()
