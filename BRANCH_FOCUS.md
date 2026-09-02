# 🎯 Branch Focus: Universal Interface Gateway & Pluggable Adapters

**Branch Name:** `feature/universal-gateway-telegram` (or `arch/universal-interface-gateway`)  
**Scope:** Strict 4-Layer Architecture Refactor, Universal Gateway Layer, CLI Adapter Decoupling, and Pluggable Telegram Integration.

---

## 1. Executive Mission

The objective of this branch is to decouple the AI Personal Assistant from direct terminal/console bindings by implementing a **Strict 4-Layer Architecture**. 

A platform-agnostic **Universal Assistant Gateway & Asynchronous Event Bus** will serve as the sole communication boundary between the assistant core engine and user interfaces. **Both the CLI REPL and remote platforms (Telegram, Discord, Webhooks) will operate as peer client adapters** connecting to this layer.

---

## 2. Core Architectural Pillars

### 1. Strict Layer Separation
- **Layer 0 (Core Engine)**: LangGraph state machine, ReAct workers, Unified Memory, and background daemons. Strictly UI-blind with zero dependencies on terminal I/O, Rich, or Telegram APIs.
- **Layer 1 (Universal Gateway)**: Central Asynchronous Event Bus, Normalized Protocol Schemas, Multi-Session Coordinator, Universal HITL & Auth Coordinator, and Proactive Notification Hub.
- **Layer 2 (Adapter Lifecycle Manager)**: Dynamic supervisor tracking adapter states (Disabled, Starting, Running, Stopping, Error) with hot-toggle start/stop controls.
- **Layer 3 (Presentation & Client Adapters)**: Independent peer adapters (CLI Adapter, Telegram Adapter, future Discord Adapter).

### 2. CLI as a First-Class Peer Adapter
- The CLI REPL is refactored from a monolithic runner into `CLIAdapter`, consuming the exact same Universal Events as remote platforms.
- Changing logging styles, debug trace formatting, or UI rendering will never break internal agent mechanics.

### 3. Dynamic Toggleable Telegram Plugin
- Run the Telegram bot as an isolated plugin that can be started, stopped, or monitored dynamically on demand (via `/plugins start telegram` or environment toggles) without restarting the assistant.
- Event-driven communication (no tight polling coupling).
- Interactive Human-in-the-Loop (HITL) approval buttons and auto-deleting password verification.
- Voice memo transcription and optional neural audio replies (Piper/Kokoro TTS).
- Proactive email alerts from the Gmail IDLE daemon with inline action callbacks (`[Draft Reply]`, `[Dismiss]`).

### 4. Zero-Friction Multi-Platform Extensibility
- Standardized Base Adapter Contract ensures adding future platforms (e.g. Discord, Slack, Web PWA) requires only adding a single adapter class in Layer 3 with **zero modifications** to the core engine or gateway.

---

## 3. Structural Layer Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Layer 3: Presentation & Client Adapters                                 │
│ 🖥️ CLI Adapter   📱 Telegram Adapter   🎮 Discord (Future)   🌐 Web/PWA │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ (Universal Inbound / Outbound Events)
┌────────────────────────────────────▼────────────────────────────────────┐
│ Layer 2: Adapter Lifecycle & Orchestration Layer                        │
│ • Plugin Lifecycle Supervisor (Start, Stop, Health Monitor, Hot Toggle)│
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│ Layer 1: Universal Assistant Gateway Layer (Contract Boundary)          │
│ • Central Asynchronous Event Bus                                        │
│ • Normalized Message & Telemetry Protocol                               │
│ • Multi-Platform Session & Context Coordinator                          │
│ • Universal Human-in-the-Loop (HITL) & Auth Event Coordinator           │
│ • Proactive Notification Dispatcher Hub                                 │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│ Layer 0: Core Engine & Background Daemons (UI-Blind Business Logic)     │
│ • LangGraph State Machine Engine (MemoryInjector, TaskRouter, Workers)  │
│ • UnifiedMemory (Vector HNSW, SQLite, Context Stores)                   │
│ • Background Daemons (Gmail IMAP IDLE, Task Scheduler)                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Implementation Phases on this Branch

| Phase | Focus Area | Key Deliverables |
| :--- | :--- | :--- |
| **Phase 1** | **Universal Gateway Layer & Event Protocol** | `src/CoreFunctions/Gateway/` (Event Bus, Protocol, Session Coordinator, HITL Coordinator, Proactive Hub) |
| **Phase 2** | **CLI Adapter Decoupling** | `src/Interfaces/CLI/` (`cli_adapter.py` refactor, routing terminal I/O strictly via Gateway events) |
| **Phase 3** | **Adapter Lifecycle Manager** | `src/Interfaces/` (`lifecycle_manager.py`, `base_adapter.py`, `/plugins` slash command family) |
| **Phase 4** | **Pluggable Telegram Adapter** | `src/Interfaces/Telegram/` (`telegram_adapter.py`, security filter, progress streamer, HITL keyboards, voice/media handlers) |
| **Phase 5** | **Proactive Daemons Integration** | Route Gmail IDLE and task scheduler events through the Gateway Proactive Hub to all active adapters |
| **Phase 6** | **End-to-End Verification** | Comprehensive testing of dynamic toggling, remote HITL approvals, cross-platform session context, and CLI parity |

---

## 5. Success Criteria

1. **Layer Boundary Integrity**: Core engine (Layer 0) contains zero display, terminal, or platform-specific dependencies.
2. **CLI Parity**: The refactored CLI operates identically in user experience, visual fidelity, and latency through the Gateway.
3. **Dynamic Plugin Toggling**: Telegram plugin can be launched, monitored, and stopped from the CLI or config without assistant restart.
4. **Interactive Remote HITL**: CAPTCHAs, dangerous tool approvals, and password prompts render as interactive buttons on Telegram and resolve without console blocking.
5. **Discord Readiness**: A future Discord adapter can be plugged in using only the Layer 3 adapter contract without altering core or gateway files.
