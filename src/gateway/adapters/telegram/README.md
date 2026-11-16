# Telegram Bot Ingress & Observer Adapter

The `telegram` package provides a production-grade Telegram Bot integration for the AI Personal Assistant backend. It functions both as an **Execution Observer** (streaming live progress and telemetry) and as a **Bidirectional Ingress Gateway Daemon** (long-polling, user authorization, interactive commands, and Human-in-the-Loop clearances).

---

## Architecture & Responsibilities (Clean Code / SRP)

```
                       ┌────────────────────────────────────────┐
                       │ Telegram API (api.telegram.org)       │
                       └───────────────────▲────────────────────┘
                                           │ Long-polling / HTTP
                       ┌───────────────────▼────────────────────┐
                       │  BotService (service.go)               │
                       │  - Long-polling daemon                 │
                       │  - Security user whitelist             │
                       │  - Interactive commands & callbacks    │
                       └───────────┬────────────────┬───────────┘
                                   │                │
            ┌──────────────────────▼───────┐   ┌────▼────────────────────────┐
            │ SessionManager (session.go)  │   │ TurnRunner (turn_runner.go) │
            │ - chat_id -> session_id      │   │ - Typing heartbeat          │
            │ - pending HITL store         │   │ - Progress updater (1s edit)│
            │ - Whitelist authorization    │   │ - Answer chunking           │
            └──────────────────────────────┘   └─────────────┬───────────────┘
                                                             │
                                               ┌─────────────▼───────────────┐
                                               │ Layer 1 Gateway             │
                                               │ (SubmitTurn / RespondHITL)  │
                                               └─────────────────────────────┘
```

### Module Breakdown
* **`types.go`**: Domain models for Telegram Bot API (`Update`, `Message`, `User`, `Chat`, `CallbackQuery`, `InlineKeyboardMarkup`, `Config`).
* **`client.go`**: `BotClient` interface, official `HTTPBotClient` implementation, and `MockBotClient` test double.
* **`formatter.go`**: Message splitting under character limits (preserving ```` ``` ```` code fences), status rendering, HITL approval prompt building, and metrics formatting.
* **`session.go`**: `SessionManager` managing per-chat sessions, HITL pending states, and authorization whitelisting.
* **`turn_runner.go`**: Manages execution turn lifecycle, typing heartbeat actions, throttled progress updates, and answer delivery.
* **`service.go`**: Long-polling background daemon routing inbound updates, interactive commands, and callback queries.
* **`adapter.go`**: Observer implementation implementing `gateway.ExecutionObserver`.
* **`env.go`**: Environment and `.env` configuration loader.

---

## Configuration

Set the following in `.env` or your process environment:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | Bot API token obtained from @BotFather | `8897267617:AAGbisy...` |
| `TELEGRAM_ALLOWED_USER_IDS` | Comma-separated list of numeric Telegram User IDs | `1909188006, 12345678` |
| `TELEGRAM_THROTTLE_MS` | Throttle interval between status message edits (ms) | `1000` |
| `TELEGRAM_POLLING_TIMEOUT_SEC` | Long-polling HTTP timeout (seconds) | `30` |

---

## Running the Telegram Adapter

### Via Assistant CLI:
```bash
go run cmd/assistant/main.go --telegram
```

### Via Dedicated Telegram Daemon:
```bash
go run cmd/telegram/main.go
```

---

## Commands & Interaction

* **Any text**: Submits an interactive turn to the assistant with live status progress and typing feedback.
* **/start**: Displays welcome message and available commands.
* **/help**: Shows operational guidance.
* **/reset** or **/clear**: Clears current conversation context and creates a fresh session.
* **/status**: Queries live phase, active agent, and subtask status from Gateway.
* **/approve `[feedback]`**: Authorizes a paused HITL action.
* **/deny `[feedback]`**: Rejects a paused HITL action.
* **Inline Buttons**: Directly click `[✅ Approve]` or `[❌ Deny]` buttons on approval prompts.
