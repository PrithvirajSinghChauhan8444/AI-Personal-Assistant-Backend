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
| **Client Adapters & Observability** | [guide/adapters/OBSERVER_ADAPTER_GUIDE.md](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/guide/adapters/OBSERVER_ADAPTER_GUIDE.md) | Full guide on building client adapters (CLI, Web, Telegram, Discord, etc.), subscribing to the Observer API, querying live state snapshots, and handling human approvals without modifying core code. |
