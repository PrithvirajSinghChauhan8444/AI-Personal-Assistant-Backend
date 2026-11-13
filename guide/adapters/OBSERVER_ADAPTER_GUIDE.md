# Modular Adapter & Observer API — Developer & Agent Integration Guide

> **Core Invariant**: **Decouple Semantics from Rendering.**
> The Layer 2 Core Orchestrator only emits *what is happening* via the **Unified Observer API**. Client adapters (CLI, Web, Mobile, Telegram, Discord, background daemons) only worry about *how to present it*.
>
> **CRITICAL RULE FOR DEVELOPERS & CODING AGENTS**:
> **DO NOT modify the core orchestrator or engine code** to change UI layout, add platform-specific formatting, or handle client-specific rate limits.
> All client features MUST be implemented as independent adapters or listeners hooked into the existing public methods described below.

---

## 1. Architectural Overview

```
                        ┌───────────────────────────────┐
                        │   Layer 2 Core Orchestrator   │
                        └───────────────┬───────────────┘
                                        │
                        ┌───────────────▼───────────────┐
                        │   Layer 1 Gateway & Hub       │
                        │    (src/gateway/gateway.go)   │
                        │    (src/gateway/observer.go)  │
                        └───────────────┬───────────────┘
                                        │
                 [ Unified Execution Observer Event Stream & Snapshot API ]
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
  ┌───────────┐                   ┌───────────┐                   ┌───────────┐
  │    CLI    │                   │    Web    │                   │ Telegram  │
  │  Adapter  │                   │ Dashboard │                   │    Bot    │
  │ (Terminal)│                   │(WS / SSE) │                   │(Throttled)│
  └───────────┘                   └───────────┘                   └───────────┘
```

---

## 2. Available Public Gateway Methods (Directly Callable)

Import package:
```go
import "assistant/src/gateway"
```

Given an initialized Gateway instance `gw := stack.Gateway`:

### A. Turn Execution & Ingress
* **`gw.SubmitTurn(ctx context.Context, raw gateway.InboundTurnRequest) (<-chan gateway.OutboundEvent, gateway.InboundTurnRequest, error)`**
  * Submits an inbound request, normalizes parameters, and returns an unbuffered read-only event channel.
  * Inbound request parameters:
    * `SessionID`: UUID string (or leave empty for auto-generation).
    * `UserID`: e.g. `"local:user"` or `"telegram:12345"`.
    * `Channel`: `gateway.ClientTypeCLI`, `ClientTypeWeb`, `ClientTypeTelegram`, `ClientTypeInternal`.
    * `Trigger`: `gateway.TriggerInteractive` (human) or `TriggerAutonomous` (background).
    * `Prompt`: User prompt or goal text.
    * `TargetAgent`: `"auto"` (orchestrated) or explicit: `"system"`, `"browser"`, `"research"`, `"productivity"`.
    * `AllowedCapabilities`: string slice for sandboxed autonomous runs.

### B. Live Snapshot & Re-sync ("What is happening right now?")
* **`gw.GetSnapshot(sessionID string) (*gateway.TurnSnapshot, error)`**
  * Returns the live state of an active or recent session without needing to replay the stream from the start.
  * Returns `gateway.ErrSnapshotNotFound` if the session does not exist.
* **`gw.GetActiveSnapshots() []*gateway.TurnSnapshot`**
  * Returns snapshots for all currently active (in-flight) turns across all sessions (Phase: `PLANNING`, `EXECUTING`, `WAITING_APPROVAL`).
* **`gw.GetAllSnapshots() []*gateway.TurnSnapshot`**
  * Returns snapshots for all tracked sessions, including completed and failed turns.

### C. Historical Logs & Diagnostics
* **`gw.GetTurnLogs(turnID string) ([]gateway.LogEntry, error)`**
  * Returns the complete diagnostic log trace for any given turn ID.
* **`gw.SetPersistentStore(store gateway.PersistentObserverStore)`**
  * Plugs in a persistent database store (e.g. SQLite, PostgreSQL) to archive operational turn logs beyond RAM limits.

### D. Observer Subscriptions (Multi-Adapter Fan-Out)
* **`gw.RegisterObserver(id string, obs gateway.ExecutionObserver) error`**
  * Attaches a listener or adapter to receive every event emitted by the backend.
* **`gw.UnregisterObserver(id string)`**
  * Detaches an existing observer.
* **`gw.ObserverHub() *gateway.ObserverHub`**
  * Accesses the underlying observer registry directly.

### E. Human-in-the-Loop (HITL) Clearances
* **`gw.RespondHITL(ctx context.Context, resp gateway.HITLResponse) error`**
  * Submits human approval or rejection for a paused turn.
  * `resp.RequestID`: Required matching request UUID.
  * `resp.Approved`: `true` to approve, `false` to reject.
  * `resp.UserFeedback`: Optional guidance or rejection reason.

---

## 3. The Execution Observer Interface

To create a new adapter or background watcher, implement the `ExecutionObserver` interface:

```go
type ExecutionObserver interface {
    OnEvent(ctx context.Context, ev gateway.OutboundEvent)
}
```

Or use the functional wrapper:
```go
obs := gateway.ObserverFunc(func(ctx context.Context, ev gateway.OutboundEvent) {
    // Process event
})
_ = gw.RegisterObserver("my_custom_watcher", obs)
```

---

## 4. Complete Event Catalog (`OutboundEvent`)

Every event delivered to `OnEvent` or the stream channel contains:

| Field | Type | Description |
| :--- | :--- | :--- |
| `Type` | `gateway.EventType` | Event category (see table below). |
| `SessionID` | `string` | Associated conversation session UUID. |
| `TurnID` | `string` | Execution turn identifier. |
| `TraceID` | `string` | Distributed trace correlation ID. |
| `Phase` | `gateway.ExecutionPhase` | Current core execution phase. |
| `AgentName` | `string` | Identity of active agent/subagent. |
| `Timestamp` | `time.Time` | UTC creation timestamp. |
| `StatusMsg` | `string` | Human-readable status update. |

### Event Types & Their Populated Payloads

| Event Type (`ev.Type`) | Populated Payload Field | Purpose |
| :--- | :--- | :--- |
| `EventPhaseChange` | `ev.Phase` | Emitted when engine transitions (`PLANNING`, `EXECUTING`, `WAITING_APPROVAL`, `COMPLETED`, `FAILED`). |
| `EventPlanCreated` | `ev.Plan` (`*gateway.PlanInfo`) | Manager Agent completed DAG task decomposition. Contains `PrimaryGoal` and `SubTasks` slice. |
| `EventPlanDiagnostic` | `ev.Diagnostic` (`*gateway.PlanDiagnosticInfo`) | Emitted when planning fails or falls back. Contains `Reason`, `Goal`, `FallbackTriggered`, `Error`. |
| `EventThoughtChunk` | `ev.TextDelta` | Agent internal monologue / reasoning stream. |
| `EventThoughtComplete` | `ev.StatusMsg` | **Boundary marker**: Agent finished thinking; switching to execution/action. |
| `EventSubtaskStart` | `ev.Subtask` (`*gateway.SubtaskEventInfo`) | A DAG subtask has begun execution. Contains `SubtaskID`, `Worker`, `Description`, `InputPrompt`. |
| `EventSubtaskProgress` | `ev.Subtask` (`*gateway.SubtaskEventInfo`) | Subtask status changed (e.g. `IN_PROGRESS`). |
| `EventSubtaskComplete` | `ev.Subtask` (`*gateway.SubtaskEventInfo`) | Subtask completed. Contains `Output`, `ArtifactPath`, `DurationMs`. |
| `EventSubtaskFailed` | `ev.Subtask` (`*gateway.SubtaskEventInfo`) | Subtask failed. Contains `Error`, `DurationMs`. |
| `EventToolCall` | `ev.ToolCall` (`*gateway.ToolCallInfo`) | Tool invocation start. Contains `CallID`, `ToolName`, `Arguments`, `ArgsJSON`. |
| `EventToolResult` | `ev.ToolResult` (`*gateway.ToolResultInfo`) | Tool execution finished. Contains `ToolName`, `ExitCode`, `Output`, `ArtifactPath`, `DurationMs`, `IsError`. |
| `EventTokenChunk` | `ev.TextDelta` | Real-time conversational response text tokens. |
| `EventHITLRequest` | `ev.HITL` (`*gateway.HITLApprovalPrompt`) | Execution paused awaiting human clearance. Contains `RequestID`, `ToolName`, `Reason`, `ArgumentsJSON`. |
| `EventSystemLog` | `ev.Log` (`*gateway.LogEntry`) | Live operational log with `Severity` (`DEBUG`, `INFO`, `WARN`, `ERROR`), `Component`, `Message`. |
| `EventTurnComplete` | `ev.Metrics` (`*gateway.TurnMetrics`) | Turn concluded. Contains `PromptTokens`, `CompletionTokens`, `TotalDurationMs`, `TimeToFirstByteMs` (or helper `ev.Metrics.TTFTMs()`). |
| `EventTurnError` | `ev.Error` | Fatal turn execution failure. |

---

## 5. State Snapshot Model (`TurnSnapshot`)

When calling `gw.GetSnapshot(sessionID)`:

```go
type TurnSnapshot struct {
    SessionID      string              // Session UUID
    TurnID         string              // Active Turn ID
    TraceID        string              // Trace ID
    Phase          ExecutionPhase      // IDLE, PLANNING, EXECUTING, WAITING_APPROVAL, COMPLETED, FAILED
    ActiveAgent    string              // "Manager", "BrowserAgent", "SystemAgent", etc.
    ActiveAction   *ActiveActionInfo   // Tool or subtask in flight right now + started_at + elapsed_ms
    Plan           *PlanInfo           // Full DAG plan and subtasks
    Subtasks       []SubtaskItemInfo   // Subtask statuses (PENDING, IN_PROGRESS, COMPLETED, FAILED)
    PendingHITL    *HITLApprovalPrompt // Active approval prompt if in WAITING_APPROVAL
    ThoughtsBuffer string              // Accumulated reasoning text so far
    AnswerBuffer   string              // Accumulated response tokens so far
    RecentLogs     []LogEntry          // Ring buffer of recent log entries
    StartedAt      time.Time           // Turn start timestamp
    UpdatedAt      time.Time           // Latest state update timestamp
}
```

### Persistent Storage Extension (`PersistentObserverStore`)

By default, operational logs and snapshots are held in bounded in-memory ring buffers (`DefaultMaxActiveSnapshots = 200`, `DefaultMaxHistoricalTurns = 100`, `DefaultMaxTurnLogs = 500`) to guarantee zero disk I/O latency on high-frequency streaming events. To persist operational audit logs into SQLite, PostgreSQL, or ClickHouse, implement:

```go
type PersistentObserverStore interface {
    SaveTurnLog(ctx context.Context, entry LogEntry) error
    GetHistoricalTurnLogs(ctx context.Context, turnID string) ([]LogEntry, error)
}
```
And attach it during initialization without modifying the core pipeline:
```go
gw.SetPersistentStore(mySqliteStore)
```

---

## 6. Built-in Adapters Reference

### A. CLI Adapter (`assistant/src/gateway/adapters/cli`)
* **Interactive REPL**:
  ```go
  adapter := cli.NewCLIAdapter(gw, os.Stdin, os.Stdout, sessionID)
  err := adapter.StartInteractive(ctx)
  ```
* **Single Turn Runner**:
  ```go
  err := cli.RunSingleTurn(ctx, gw, inboundReq, os.Stdout)
  ```
* **Stream Renderer (ANSI / Claude Code styled rendering)**:
  ```go
  renderer := cli.NewStreamRenderer(os.Stdout)
  renderer.RenderEvent(ev)
  renderer.Flush()
  ```

### B. Web Adapter (`assistant/src/gateway/adapters/web`)
* **Initialize and Mount**:
  ```go
  webAdapter := web.NewWebAdapter(gw)
  
  // As standard http.Handler:
  http.Handle("/", webAdapter.Handler())
  
  // Or standalone server:
  go webAdapter.Start(":8080")
  ```
* **HTTP Endpoints**:
  * `POST /api/turn`: Submit turn (`{"session_id": "...", "prompt": "..."}`) -> returns `202 Accepted`.
  * `GET /api/snapshot?session_id=...`: Point-in-time snapshot JSON for real-time frontend rendering.
  * `GET /api/logs?turn_id=...`: Diagnostic logs for past turns.
  * `POST /api/hitl`: Human-in-the-loop clearance (`{"request_id": "...", "approved": true}`).
  * `GET /api/stream?session_id=...`: Server-Sent Events (SSE) streaming JSON events.
  * `GET /ws?session_id=...`: RFC 6455 WebSocket streaming JSON events and receiving client inputs.

### C. Telegram Adapter (`assistant/src/gateway/adapters/telegram`)
* **Initialize**:
  ```go
  client := telegram.NewHTTPBotClient(botToken, nil)
  adapter, err := telegram.NewTelegramAdapter(telegram.Config{
      Client:           client,
      ChatID:           chatID,
      ThrottleInterval: 1 * time.Second, // Throttles message edits to respect rate limits
  })
  _ = gw.RegisterObserver("telegram", adapter)
  ```

---

## 7. How-To Recipes for Developers & Agents

### Recipe 1: Building a Custom Adapter in 15 Lines (e.g. Discord / Slack / WebSocket)
Never touch the orchestrator! Simply implement `OnEvent`:

```go
package myadapter

import (
    "context"
    "fmt"
    "assistant/src/gateway"
)

type DiscordAdapter struct {
    channelID string
}

func (d *DiscordAdapter) OnEvent(ctx context.Context, ev gateway.OutboundEvent) {
    switch ev.Type {
    case gateway.EventSubtaskStart:
        fmt.Printf("[Discord] ➜ Subtask started: %s\n", ev.Subtask.Description)
    case gateway.EventToolCall:
        fmt.Printf("[Discord] 🛠 Tool: %s\n", ev.ToolCall.ToolName)
    case gateway.EventTurnComplete:
        fmt.Printf("[Discord] ✔ Done in %dms\n", ev.Metrics.TotalDurationMs)
    }
}
```
Attach to Gateway:
```go
gw.RegisterObserver("discord", &DiscordAdapter{channelID: "12345"})
```

### Recipe 2: Frontend Dashboard (Connecting over WebSocket)
```javascript
const socket = new WebSocket("ws://localhost:8080/ws?session_id=" + sessionID);

socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    // First message on connect is the snapshot
    if (data.phase && data.subtasks) {
        renderDAGGraph(data.plan);
        return;
    }
    
    // Live events
    switch (data.type) {
        case "PHASE_CHANGE":
            updateStatusBadge(data.phase);
            break;
        case "PLAN_CREATED":
            renderDAGGraph(data.plan);
            break;
        case "SUBTASK_PROGRESS":
            updateSubtaskNode(data.subtask.subtask_id, data.subtask.status);
            break;
        case "TOKEN_CHUNK":
            appendMarkdownText(data.text_delta);
            break;
        case "TOOL_CALL":
            highlightActiveTool(data.tool_call.tool_name);
            break;
        case "HITL_REQUEST":
            showApprovalModal(data.hitl);
            break;
    }
};
```

### Recipe 3: Checking System State at Any Moment
```go
snap, err := gw.GetSnapshot(sessionID)
if err != nil {
    log.Println("Session is idle or not found")
    return
}
fmt.Printf("Phase: %s, Active Agent: %s\n", snap.Phase, snap.ActiveAgent)
if snap.ActiveAction != nil {
    fmt.Printf("Active Tool: %s (running for %dms)\n", snap.ActiveAction.Name, snap.ActiveAction.ElapsedMs)
}
```

---

## 8. Summary Checklist Before Changing Code

- [ ] Are you adding formatting for a client? **Create or modify an adapter in `src/gateway/adapters/`**, not the orchestrator.
- [ ] Do you need to know backend state? **Use `gw.GetSnapshot(sessionID)`**, do not query internal SQLite tables or scheduler pointers directly.
- [ ] Do you need to capture events? **Register an `ExecutionObserver`**, do not intercept internal bridge channels.
- [ ] Do you need to approve an action? **Call `gw.RespondHITL(ctx, resp)`**.
