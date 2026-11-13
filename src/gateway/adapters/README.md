# Client Adapters & Execution Observer API

This directory contains client adapters connecting external interfaces to the AI Personal Assistant backend via the **Unified Execution Observer API**.

## Available Adapters

* **[CLI Adapter (`cli/`)](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/gateway/adapters/cli)**: Interactive terminal REPL and single-turn command line runner with Claude Code style ANSI formatting and live token streaming.
* **[Web Adapter (`web/`)](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/gateway/adapters/web)**: High-performance HTTP REST, Server-Sent Events (SSE), and RFC 6455 WebSocket streaming server for web dashboards and mobile clients.
* **[Telegram Adapter (`telegram/`)](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/gateway/adapters/telegram)**: Throttled Telegram Bot observer that updates in-flight progress messages and delivers final synthesized answers.

## Developer & Agent Integration Guide

For full instructions, architecture rules, public methods, and recipes on building custom adapters without modifying core engine code, read the **[Observer Adapter Guide](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/guide/adapters/OBSERVER_ADAPTER_GUIDE.md)**.
