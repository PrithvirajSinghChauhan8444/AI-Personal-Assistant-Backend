"""Lightweight, zero-dependency Python MCP Server base class for local stdio JSON-RPC 2.0 communication."""

import json
import sys
from typing import Any, Callable, Dict


class SimpleMCPServer:
    """Manages an MCP stdio server conforming to the MCP 2024-11-05 protocol."""

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], str],
    ):
        """Registers a tool with metadata and its execution handler."""
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "handler": handler,
        }

    def run(self):
        """Main event loop: reads JSON-RPC requests from stdin and writes responses to stdout."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                req = json.loads(line)
            except Exception:
                continue

            method = req.get("method")
            req_id = req.get("id")

            if method == "initialize":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": self.name, "version": self.version},
                    },
                }
                self._send(res)
            elif method == "notifications/initialized":
                # Client acknowledgment notification; no response required
                pass
            elif method == "tools/list":
                tools_list = [
                    {
                        "name": t["name"],
                        "description": t["description"],
                        "inputSchema": t["inputSchema"],
                    }
                    for t in self.tools.values()
                ]
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": tools_list},
                }
                self._send(res)
            elif method == "tools/call":
                params = req.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})

                if tool_name not in self.tools:
                    self._send({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32601,
                            "message": f"Tool '{tool_name}' not found",
                        },
                    })
                    continue

                try:
                    handler = self.tools[tool_name]["handler"]
                    output_text = handler(arguments)
                    self._send({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": str(output_text)}],
                            "isError": False,
                        },
                    })
                except Exception as e:
                    self._send({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": f"Error executing {tool_name}: {e}"}],
                            "isError": True,
                        },
                    })

    def _send(self, data: Dict[str, Any]):
        sys.stdout.write(json.dumps(data) + "\n")
        sys.stdout.flush()
