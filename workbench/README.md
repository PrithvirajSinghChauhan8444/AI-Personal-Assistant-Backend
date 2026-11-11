# Module Workbench & Flight Recorder

A visual, web-based, zero-external-runtime developer workbench and flight recorder for the assistant backend architecture.

## Features

- **Zero-Boilerplate Module Testing**: Test any module or multi-layer pipeline directly in the browser without writing separate unit test files, fixtures, or assertions.
- **Dynamic Parameter Introspection**: Automatically discovers input fields, types (`string`, `enum`, `[]string`, `bool`), and constraints via reflection.
- **Live Event Multiplexing**: Streams real-time channels (`TOKEN_CHUNK`, `THOUGHT_CHUNK`, `STATUS_UPDATE`, `TURN_COMPLETE`, `TURN_ERROR`) over Server-Sent Events (SSE).
- **Interactive Human-In-The-Loop (HITL)**: When a tool triggers an approval request, an interactive modal appears with **[Approve]** and **[Deny]** controls that dispatch back in real time.
- **Comprehensive Request Telemetry & Go Logs**: Real-time observability tracking every HTTP API request (method, status, duration in µs, bytes in/out, payload, headers, and trace IDs) as well as internal Go subsystem logs (`gateway`, `orchestrator`, `sqlite_store`, `supervisor`) with live streaming over SSE.
- **Runtime Resource Profiling**: Inspects active Goroutines, Heap memory allocations, GC cycles, and per-execution memory/goroutine deltas to catch leaks instantly.
- **Process Supervision & Abort**: Cancel in-flight execution contexts anytime via the **[Abort / Kill]** button to test context timeouts, cancellation handling, and channel shutdown.
- **Panic Protection**: Safe recover tap catches panics and displays the exact stack trace with file and line numbers without crashing the server.
- **Disk Flight Recorder**: Persists all runs and unadulterated outputs to `workspace/workbench/history.jsonl` for auditability and 1-click replaying.
- **Embedded Self-Contained Deployment**: Built with modern React and compiled into Go's standard library `net/http` via `embed.FS`. Runs offline with zero external runtime dependencies.

---

## Quickstart

Run the workbench with a single command:

```bash
go run ./workbench/cmd/bench-ui
```

Or using the shorthand entry point:

```bash
go run ./cmd/bench-ui
```

Then open your browser to:
```text
http://localhost:8080
```

To run on a custom port or change the flight recording directory:
```bash
go run ./workbench/cmd/bench-ui -port 9000 -history-dir /path/to/logs
```

---

## Registered Modules Out-of-the-Box

1. **Layer 1: Gateway (`SubmitTurn` - Isolated)**
   - Tests Inbound normalization, agent prefix extraction, capability verification, and streaming OutboundEvents.
2. **Layer 1: Gateway (`NormalizeInbound`)**
   - Direct unit testing of the normalization algorithm and default UUID generation.
3. **Layer 2: Orchestrator (`ExecuteTurn` - Isolated)**
   - Runs Layer 2 Orchestrator directly against persistent SQLite and the Planner.
4. **Layer 2: Safety Gatekeeper (`Evaluate`)**
   - Evaluates tool safety against `INTERACTIVE` vs `AUTONOMOUS` trigger modes and capability scopes.
5. **Layer 2: Session Store**
   - Direct execution of `GetOrCreateSession`, `AppendMessage`, and `GetSessionHistory`.
6. **E2E Pipeline (`Gateway -> Orchestrator`)**
   - Full live multi-layer pipeline execution.

---

## Adding a New Module (Zero-Boilerplate Extensibility)

Registering a new layer or module takes just a few lines:

```go
bench.Register(engine.Module{
    ID:          "layer3_tool_engine",
    Name:        "Layer 3: Tool Engine (ExecuteTool)",
    Category:    "Isolated Module",
    Description: "Executes tool directly with input arguments",
    InputType:   reflect.TypeOf(ToolExecutionInput{}),
    Presets: []engine.Preset{
        {
            ID:       "sys_info",
            Name:     "System Info Query",
            Category: "Happy Path",
            Payload:  ToolExecutionInput{ToolName: "sys_info"},
        },
    },
    Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
        var input ToolExecutionInput
        if err := json.Unmarshal(inputRaw, &input); err != nil {
            return nil, err
        }
        return toolEngine.Execute(ctx, input)
    },
})
```

---

## Modifying the React UI (Optional)

If you wish to make changes to the frontend UI components:

```bash
cd workbench/ui
npm install
npm run dev    # Starts Vite dev server on http://localhost:3000 (proxies /api to 8080)
npm run build  # Recompiles directly into workbench/web/dist for Go embedding
```
