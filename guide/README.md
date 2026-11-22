# AI Personal Assistant — Developer & Agent Guides

This directory contains official integration guides, architecture contracts, and recipes for developers and autonomous coding agents.

## Purpose

> **CRITICAL RULE FOR DEVELOPERS & CODING AGENTS**:  
> **DO NOT modify the core orchestrator or engine code** to change UI layout, add platform-specific formatting, or handle client-specific rate limits.  
> Always use the documented public methods, contracts, and observer hooks.

---

## Guide Index

| Topic / Subfolder | Guide File | Description |
| :--- | :--- | :--- |
| **Client Adapters & Observability** | [adapters/OBSERVER_ADAPTER_GUIDE.md](adapters/OBSERVER_ADAPTER_GUIDE.md) | Full guide on building client adapters (CLI, Web, Telegram, Discord, etc.), subscribing to the Observer API, querying live state snapshots, and handling human approvals without modifying core code. |
| **Specialist Agents (`BaseAgent`)** | [BASE_AGENT_DEVELOPMENT_GUIDE.md](BASE_AGENT_DEVELOPMENT_GUIDE.md) | Standard specification on creating and registering Layer 6 Specialist Worker Agents using `BaseAgent`, modular subsystems, explicit tool declaration (no auto-discovery), polyglot `ToolDispatcher` (Python Local, Go Native IPC, MCP Bridge), declarative manifests, and ReAct execution loops. |
| **Tool Development & AgentTools** | [TOOL_DEVELOPMENT_GUIDE.md](TOOL_DEVELOPMENT_GUIDE.md) | Comprehensive standard for building, registering, and testing tools using the co-located multi-tool architecture with explicit `ToolDispatcher` routing across Python-local (0ms IPC), Go-native (Layer 4 IPC), and remote MCP bridges. |
