#!/usr/bin/env python3
"""
Modular AI Assistant Runner.
Interactive REPL and single-query CLI for the complete 12-worker modular pipeline.
Features:
- Checkpointing on abrupt closure / crash recovery
- Session context persistence and conversation resume
- Dynamic Google account grounding and structured error reporting
- Live verbose stream tracing & diagnostic logs
"""

import sys
import os
import json
import uuid

# Ensure root directory is in sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from modules.integration.application_orchestrator import ApplicationOrchestrator

BANNER = r"""
╭──────────────────────────────────────────────────────────╮
│  🤖 Modular Personal Assistant — All 12 Workers Active   │
│  Type your query or '/help' for commands, 'exit' to quit │
╰──────────────────────────────────────────────────────────╯
"""

HELP_TEXT = """
Available Commands:
  /remote_control [start|stop|status]  Toggle or manage Remote Control mode (CLI + Telegram)
  /remote                              Alias for /remote_control
  /export                              Export conversation (Clean/Verbose to Terminal/File)
  /verbose                             Toggle live node-by-node execution logs (ON/OFF)
  /logs [n]                            View the last [n] execution entries (default: 10)
  /history                             View previous turns in the current conversation
  /workers                             List all 12 registered modular workers and their categories
  /session                             Print the current session / thread ID
  /new                                 Start a new conversation thread session
  /help                                Show this help message
  exit, quit                           Exit the assistant
"""

def handle_remote_command(
    coordinator,
    orchestrator,
    session_id,
    chat_history,
    working_memory,
    completed_tasks,
    cmd_args: str = "",
):
    """Handles /remote and /remote_control slash commands."""
    from modules.adapters.remote_control.coordinator import RemoteControlCoordinator
    subcmd = cmd_args.strip().lower()

    if subcmd in ("stop", "off", "disable"):
        if not coordinator:
            print("\n⚠️ Remote Control is not currently active.\n")
            return None
        coordinator.stop()
        print("\n🛑 Remote Control disabled. Returning to pure CLI mode.\n")
        return None

    if coordinator and subcmd not in ("start", "on", "enable"):
        active = (coordinator.active_source or "None").upper()
        bot_running = coordinator.telegram_adapter and coordinator.telegram_adapter.is_running()
        status_str = "🟢 Online (Background Polling)" if bot_running else "🟡 Initializing / Standby"
        allowed = list(coordinator.telegram_adapter.allowed_user_ids) if coordinator.telegram_adapter else []

        print("\n" + "─" * 56)
        print("🌐 REMOTE CONTROL MODE (ACTIVE)")
        print(f"• Session ID      : {coordinator.session_id}")
        print(f"• Active Source   : {active}")
        print(f"• Total Turns     : {len(coordinator.turns)}")
        print(f"• Messages Count  : {len(coordinator.chat_history)}")
        print(f"• Telegram Status : {status_str}")
        if allowed:
            print(f"• Authorized Users: {allowed}")
        print("─" * 56)
        print("💡 Commands: /remote status | /remote stop\n")
        return coordinator

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    raw_allowed_ids = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
    allowed_ids = [int(i.strip()) for i in raw_allowed_ids.split(",") if i.strip().isdigit()]

    if not token:
        print("\n❌ Cannot start Remote Control: TELEGRAM_BOT_TOKEN is not configured in .env.")
        print("   1. Open .env and add:")
        print("        TELEGRAM_BOT_TOKEN=your_bot_token_here")
        print("        TELEGRAM_ALLOWED_USER_IDS=your_user_id")
        print("   2. Run /remote again to activate without restarting.\n")
        return coordinator

    print("\n🚀 Activating Remote Control Mode mid-conversation...")
    new_coordinator = RemoteControlCoordinator(
        orchestrator=orchestrator,
        session_id=session_id,
        chat_history=chat_history,
        working_memory=working_memory,
        completed_tasks=completed_tasks,
    )

    def on_source_shift(old_src: str, new_src: str):
        if new_src == "telegram":
            print(f"\n[Remote Control] 📲 Active conversation shifted to Telegram. Continuing in shared session...")
        elif new_src == "cli":
            print(f"\n[Remote Control] 🖥️ Active conversation shifted to CLI.")

    new_coordinator.register_shift_listener(on_source_shift)

    try:
        new_coordinator.start_telegram_background(token=token, allowed_user_ids=allowed_ids)
        print(f"✔ Remote Control is now ACTIVE!")
        print(f"• Connected Session: {session_id} ({len(chat_history)} previous messages preserved)")
        print("• Telegram bot is listening in background.")
        print("• When you query on Telegram, the conversation will shift there seamlessly.\n")
        return new_coordinator
    except Exception as e:
        print(f"\n❌ Failed to start background Telegram adapter: {e}\n")
        return coordinator


def handle_export_command(coordinator_or_orchestrator, session_id, chat_history, cmd_args=""):
    """Rule 2: On-demand conversation export (clean/verbose to terminal/file)."""
    from modules.adapters.remote_control.exporter import ConversationExporter
    args = cmd_args.strip().split()
    verbose = None
    save_file = None

    for a in args:
        al = a.lower()
        if al in ("-v", "--verbose", "verbose"):
            verbose = True
        elif al in ("--clean", "clean"):
            verbose = False
        elif al in ("-f", "--file", "file"):
            save_file = True
        elif al in ("-p", "--print", "print", "terminal"):
            save_file = False

    if verbose is None:
        print("\n" + "─" * 48)
        print("📄 Export Conversation Transcript")
        print("  [1] Standard (Clean user & assistant messages)")
        print("  [2] Verbose (Detailed execution with worker subtasks & nodes)")
        choice = input("Select format (1 or 2, default 1): ").strip()
        verbose = (choice == "2")

    if save_file is None:
        print("\nOutput Destination:")
        print("  [1] Print on terminal")
        print("  [2] Save as a file")
        choice = input("Select destination (1 or 2, default 1): ").strip()
        save_file = (choice == "2")

    if hasattr(coordinator_or_orchestrator, "export_conversation_to_file"):
        if save_file:
            file_path = coordinator_or_orchestrator.export_conversation_to_file(verbose=verbose)
            print(f"\n✔ Conversation export saved to:\n  📂 {file_path}\n")
        else:
            content = coordinator_or_orchestrator.export_conversation(verbose=verbose)
            print("\n" + "=" * 62)
            print(content)
            print("=" * 62 + "\n")
    else:
        content = ConversationExporter.format_clean(
            session_id=session_id,
            turns=[],
            active_source="CLI",
            chat_history=chat_history,
        )
        if save_file:
            file_path = ConversationExporter.save_to_file(content, session_id, verbose=verbose)
            print(f"\n✔ Conversation export saved to:\n  📂 {file_path}\n")
        else:
            print("\n" + "=" * 62)
            print(content)
            print("=" * 62 + "\n")


def print_workers(orchestrator: ApplicationOrchestrator):
    print("\n📦 Registered Modular Workers:")
    for w in orchestrator.workers:
        print(f"  • {w.name:<22} [{', '.join(w.categories)}]")
    print()

def show_recent_logs(num_entries: int = 10):
    log_file = os.path.join(WORKSPACE_ROOT, "Memory", "logs", "modular_execution.jsonl")
    if not os.path.exists(log_file):
        print("\n⚠️ No execution log file found at Memory/logs/modular_execution.jsonl\n")
        return

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        recent = lines[-num_entries:]
        print(f"\n📜 Last {len(recent)} Execution Log Entries ({log_file}):")
        for line in recent:
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp", "").split("T")[-1][:8]
                mod = entry.get("module", "")
                evt = entry.get("event", "")
                data = entry.get("data", {})
                
                summary = ""
                if evt == "session_start":
                    summary = f"Goal: {data.get('goal', '')}"
                elif evt == "session_error":
                    summary = f"ERROR: {data.get('error', '')}"
                elif "active_subtasks" in data:
                    summary = f"Subtasks: {len(data['active_subtasks'])} items"
                elif "next_node" in data:
                    summary = f"Route -> {data['next_node']}"
                elif "completed_tasks" in data:
                    for tid, tval in data["completed_tasks"].items():
                        summary = f"Done [{tid}]: {tval.get('summary', '')[:60]}..."
                elif "final_response" in data:
                    summary = f"Final Answer ({len(data['final_response'])} chars)"
                else:
                    summary = str(data)[:60]

                print(f"  [{ts}] {mod:<22} {evt:<18} {summary}")
            except Exception:
                print(f"  {line.strip()[:100]}")
        print()
    except Exception as e:
        print(f"\n❌ Failed to read logs: {e}\n")

def check_interrupted_checkpoint(orchestrator: ApplicationOrchestrator):
    """Checks and handles recovery for tasks interrupted by abrupt exit or crash."""
    interrupted = orchestrator.get_interrupted_checkpoint()
    if not interrupted:
        return None

    goal = interrupted.get("primary_goal", "Unknown Goal")
    status = interrupted.get("status", "interrupted")
    completed = interrupted.get("completed_tasks", {})
    subtasks = interrupted.get("active_subtasks", [])

    print("\n" + "=" * 62)
    print("⚠️  PREVIOUS INTERRUPTED TASK DETECTED")
    print(f"• Goal      : {goal}")
    print(f"• Status    : {status}")
    print(f"• Progress  : {len(completed)} / {len(subtasks)} subtask(s) completed")
    print("=" * 62)
    print("  [1] 🔄 Resume Interrupted Task")
    print("  [2] 🗑️  Discard Checkpoint and Start Fresh")
    
    choice = input("\nSelect Option (1 or 2, default 1): ").strip()
    if choice == "2":
        orchestrator.clear_interrupted_checkpoint()
        print("✔ Cleared checkpoint.\n")
        return None
    
    print("✔ Resuming interrupted execution...\n")
    return interrupted

def check_saved_session(orchestrator: ApplicationOrchestrator):
    """Checks and prompts user to restore context from previous conversation."""
    saved = orchestrator.get_saved_session()
    if not saved:
        return [], {}, {}

    history = saved.get("chat_history", [])
    wm = saved.get("working_memory", {})
    completed = saved.get("completed_tasks", {})
    summary = saved.get("session_summary", "")

    if not history:
        return [], {}, {}

    print("\n" + "=" * 62)
    print("✦ PREVIOUS CONVERSATION DETECTED")
    print(f"• Conversation Turns : {len(history)} messages restored")
    if summary:
        print(f"• Summary            : {summary[:120]}...")
    print("=" * 62)
    print("  [1] 🆕 Start New Chat (Fresh context)")
    print("  [2] 🔄 Continue Previous Session (Restore context)")
    
    choice = input("\nSelect Option (1 or 2, default 2): ").strip()
    if choice == "1":
        orchestrator.clear_saved_session()
        print("✔ Starting fresh new session.\n")
        return [], {}, {}

    print(f"✔ Resumed previous session ({len(history)} turns restored).\n")
    return history, wm, completed

CLI_HELP = """Usage: python run_modular.py [OPTIONS] [QUERY]

Options:
  -h, --help                          Show this help message and exit
  -v, --verbose                       Enable live node-by-node execution logs
  -r, --remote, --remote-control      Launch dual CLI + Telegram Remote Control session
  -t, --telegram, --telegram-service  Start the Telegram bot as a separate service
  -d, --daemon                        Run service as a detached background daemon
"""

def start_telegram_service(daemon: bool = False):
    """Starts the Telegram bot as a separate service (foreground or detached daemon)."""
    if daemon:
        import subprocess
        log_dir = os.path.join(WORKSPACE_ROOT, "Memory", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "telegram_service.log")
        out_f = open(log_file, "a", encoding="utf-8")

        cmd = [sys.executable, os.path.abspath(__file__), "--telegram-service"]
        proc = subprocess.Popen(
            cmd,
            stdout=out_f,
            stderr=out_f,
            start_new_session=True,
            cwd=WORKSPACE_ROOT,
        )
        print("\n" + "─" * 58)
        print("🚀 TELEGRAM BOT SERVICE STARTED AS BACKGROUND DAEMON")
        print(f"• Process ID (PID) : {proc.pid}")
        print(f"• Log File         : {log_file}")
        print(f"• Stop command     : kill {proc.pid}")
        print("─" * 58 + "\n")
        return

    import run_telegram
    run_telegram.main()

def main():
    args = sys.argv[1:]

    # Help flag
    if "-h" in args or "--help" in args:
        print(CLI_HELP)
        return

    # Daemon flag for services
    daemon_mode = False
    if "-d" in args or "--daemon" in args or "--background" in args:
        daemon_mode = True
        args = [a for a in args if a not in ("-d", "--daemon", "--background")]

    # Telegram separate service flag
    tg_flags = ("-t", "--telegram", "--telegram-service", "--bot-service")
    if any(a in args for a in tg_flags):
        start_telegram_service(daemon=daemon_mode)
        return

    verbose = False
    if "-v" in args or "--verbose" in args:
        verbose = True
        args = [a for a in args if a not in ("-v", "--verbose")]

    remote_control = False
    if any(a in args for a in ("-r", "--remote", "--remote-control")):
        remote_control = True
        args = [a for a in args if a not in ("-r", "--remote", "--remote-control")]

    orchestrator = ApplicationOrchestrator()

    # If query passed as CLI arguments, run single-shot mode
    if args:
        query = " ".join(args)
        print(f"\n🎯 Query: {query}\n")
        response = orchestrator.run(query, verbose=verbose)
        print(f"\n🤖 Assistant:\n{response}\n")
        return

    # Interactive REPL mode
    print(BANNER)

    # Start background Gmail IDLE daemon for real-time autonomous email detection & response
    daemon_manager = None
    if os.environ.get("DISABLE_GMAIL_DAEMON", "").lower() not in ("1", "true", "yes"):
        try:
            from src.CoreFunctions.Integrations.Gmail.gmail_idle_daemon import GmailIdleDaemonManager
            daemon_manager = GmailIdleDaemonManager()
            daemon_manager.start_all()
        except Exception as dm_err:
            print(f"⚠️ [Gmail IDLE] Notice: Background daemon not started: {dm_err}")

    
    # 1. Check for interrupted task recovery
    interrupted = check_interrupted_checkpoint(orchestrator)
    chat_history = []
    working_memory = {}
    completed_tasks = {}

    if interrupted:
        query = interrupted.get("primary_goal", "")
        working_memory = interrupted.get("working_memory", {})
        completed_tasks = interrupted.get("completed_tasks", {})
        chat_history = interrupted.get("chat_history", [])
        session_id = f"cli_{uuid.uuid4().hex[:8]}"
        print(f"Resuming Task: {query}")
        response = orchestrator.run(
            query,
            thread_id=session_id,
            verbose=verbose,
            chat_history=chat_history,
            working_memory=working_memory,
            completed_tasks=completed_tasks
        )
        print(f"\n🤖 Assistant:\n{response}\n")
    else:
        # 2. Check for conversation session restore
        chat_history, working_memory, completed_tasks = check_saved_session(orchestrator)

    session_id = f"cli_{uuid.uuid4().hex[:8]}"
    coordinator = None
    if remote_control:
        coordinator = handle_remote_command(
            coordinator=None,
            orchestrator=orchestrator,
            session_id=session_id,
            chat_history=chat_history,
            working_memory=working_memory,
            completed_tasks=completed_tasks,
            cmd_args="start",
        )
        if coordinator:
            session_id = coordinator.session_id

    print(f"Session Thread: {session_id}")
    print(f"Live Verbose Logs: {'ON' if verbose else 'OFF'} (toggle with /verbose)\n")

    try:
        while True:
            try:
                user_input = input("You > ").strip()
                if not user_input:
                    continue

                if user_input.lower() in ("exit", "quit", ":q"):
                    print("\nGoodbye!")
                    break

                if user_input == "/help":
                    print(HELP_TEXT)
                    continue

                if user_input.startswith("/remote") or user_input.startswith("/remote_control"):
                    cmd_part = user_input.split(maxsplit=1)
                    subcmd = cmd_part[1] if len(cmd_part) > 1 else ""
                    coordinator = handle_remote_command(
                        coordinator=coordinator,
                        orchestrator=orchestrator,
                        session_id=session_id,
                        chat_history=chat_history,
                        working_memory=working_memory,
                        completed_tasks=completed_tasks,
                        cmd_args=subcmd,
                    )
                    if coordinator:
                        session_id = coordinator.session_id
                    continue

                if user_input.startswith("/export"):
                    cmd_args = user_input[len("/export"):].strip()
                    handle_export_command(coordinator or orchestrator, session_id, chat_history, cmd_args)
                    continue

                if user_input == "/verbose":
                    verbose = not verbose
                    print(f"\nLive Verbose Logs are now: {'ON' if verbose else 'OFF'}\n")
                    continue

                if user_input == "/history":
                    active_hist = coordinator.chat_history if coordinator else chat_history
                    if not active_hist:
                        print("\nNo previous turns in this conversation yet.\n")
                    else:
                        print(f"\n📜 Current Conversation History ({len(active_hist)} messages):")
                        for msg in active_hist:
                            src = f" [{msg.get('source', '').upper()}]" if msg.get("source") else ""
                            role_symbol = f"🧑 You{src}" if msg["role"] == "user" else "🤖 Assistant"
                            print(f"  {role_symbol}: {msg['content'][:120]}...")
                        print()
                    continue

                if user_input.startswith("/logs"):
                    parts = user_input.split()
                    n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
                    show_recent_logs(n)
                    continue

                if user_input == "/workers":
                    print_workers(orchestrator)
                    continue

                if user_input == "/session":
                    active_sess = coordinator.session_id if coordinator else session_id
                    print(f"\nCurrent Session ID: {active_sess}\n")
                    continue

                if user_input == "/new":
                    session_id = f"cli_{uuid.uuid4().hex[:8]}"
                    chat_history = []
                    working_memory = {}
                    completed_tasks = {}
                    if coordinator:
                        coordinator.session_id = session_id
                        coordinator.chat_history.clear()
                        coordinator.working_memory.clear()
                        coordinator.completed_tasks.clear()
                        coordinator.turns.clear()
                    orchestrator.clear_saved_session()
                    orchestrator.clear_interrupted_checkpoint()
                    print(f"\nStarted new session: {session_id} (context cleared)\n")
                    continue

                if not verbose:
                    print("\n⏳ Processing request through router, scheduler & workers...")
                else:
                    print("\n⏳ Executing pipeline stream:")

                if coordinator:
                    response = coordinator.execute_query(
                        user_prompt=user_input,
                        source="cli",
                        verbose=verbose,
                    )
                    chat_history = coordinator.chat_history
                    working_memory = coordinator.working_memory
                    completed_tasks = coordinator.completed_tasks
                else:
                    response = orchestrator.run(
                        user_prompt=user_input,
                        thread_id=session_id,
                        verbose=verbose,
                        chat_history=chat_history,
                        working_memory=working_memory,
                        completed_tasks=completed_tasks
                    )
                    chat_history.append({"role": "user", "content": user_input, "source": "cli"})
                    if response:
                        chat_history.append({"role": "assistant", "content": response, "source": "cli"})

                print(f"\n🤖 Assistant:\n{response}\n")

            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
    finally:
        if coordinator:
            try:
                print("🛑 Stopping background Telegram adapter...")
                coordinator.stop()
            except Exception:
                pass
        if daemon_manager:
            try:
                print("🛑 Stopping background Gmail daemons...")
                daemon_manager.stop_all()
            except Exception:
                pass

if __name__ == "__main__":
    main()
