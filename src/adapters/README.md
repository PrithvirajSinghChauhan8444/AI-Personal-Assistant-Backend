# Client Adapters & Execution Observer API

This directory contains client adapters connecting external interfaces to the AI Personal Assistant backend via the **Unified Execution Observer API**.

## Available Adapters

* **[CLI Adapter (`cli/`)](cli/)**: Interactive terminal REPL and single-turn command line runner with Claude Code style ANSI formatting and live token streaming.
* **[TUI Adapter (`tui/`)](tui/)**: Dual-pane terminal user interface with type-ahead suggestions for `/` commands and `@` agents, hardware cursor editing, and clean isolation between actual responses and operational telemetry logs.
* **[Web Adapter (`web/`)](web/)**: High-performance HTTP REST, Server-Sent Events (SSE), and RFC 6455 WebSocket streaming server for web dashboards and mobile clients.
* **[Telegram Adapter (`telegram/`)](telegram/)**: Throttled Telegram Bot observer that updates in-flight progress messages and delivers final synthesized answers.

## Developer & Agent Integration Guide

For full instructions, architecture rules, public methods, and recipes on building custom adapters without modifying core engine code, read the **[Observer Adapter Guide](../../../guide/adapters/OBSERVER_ADAPTER_GUIDE.md)**.
