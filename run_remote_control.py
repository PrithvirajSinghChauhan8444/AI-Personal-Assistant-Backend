#!/usr/bin/env python3
"""
Launcher for AI Personal Assistant Remote Control Mode.
Enables simultaneous CLI and Telegram interaction within the same unified session.

Features:
- Shared Conversational Session: CLI and Telegram share history, memory, and workers.
- Selective Transfer (Rule 1): Context shifts only when the user queries from the other source.
- On-Demand Export (Rule 2): Export clean or verbose transcripts to terminal, file, or Telegram.
"""

import json
import logging
import os
import sys
import uuid
from dotenv import load_dotenv

# Ensure root directory is in sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

load_dotenv()

from modules.adapters.remote_control.coordinator import RemoteControlCoordinator
from modules.integration.application_orchestrator import ApplicationOrchestrator

BANNER = r"""
╭──────────────────────────────────────────────────────────╮
│  🌐 Remote Control Mode — Dual CLI + Telegram Gateway    │
│  Single Session • Context Shifts on Query • Dual Export  │
╰──────────────────────────────────────────────────────────╯
"""

HELP_TEXT = """
Available Commands:
  /remote_control        View Remote Control status & active conversation source
  /remote                Alias for /remote_control
  /export [type] [dest]  Export conversation (Clean/Verbose to Terminal/File)
  /status                View session status
  /verbose               Toggle live node-by-node execution logs (ON/OFF)
  /history               View previous turns in the shared conversation
  /workers               List all 12 registered modular workers
  /session               Print the current shared session / thread ID
  /new                   Reset conversation context & start a fresh session
  /help                  Show this help reference
  exit, quit             Stop remote control and exit gracefully
"""


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


def handle_export_command(coordinator: RemoteControlCoordinator, cmd_args: str = ""):
    """
    Rule 2: On-demand conversation export for terminal or file, with clean or verbose options.
    """
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

    if save_file:
        file_path = coordinator.export_conversation_to_file(verbose=verbose)
        print(f"\n✔ Conversation export saved to:\n  📂 {file_path}\n")
    else:
        content = coordinator.export_conversation(verbose=verbose)
        print("\n" + "=" * 62)
        print(content)
        print("=" * 62 + "\n")


def print_remote_status(coordinator: RemoteControlCoordinator):
    active = (coordinator.active_source or "None").upper()
    bot_status = "🟢 Connected (Background Polling)" if coordinator.telegram_adapter and coordinator.telegram_adapter.is_running() else "🟡 Standby / Token not set"
    allowed = list(coordinator.telegram_adapter.allowed_user_ids) if coordinator.telegram_adapter else []

    print("\n" + "─" * 56)
    print("🌐 REMOTE CONTROL SESSION STATUS")
    print(f"• Session ID      : {coordinator.session_id}")
    print(f"• Active Source   : {active}")
    print(f"• Total Turns     : {len(coordinator.turns)}")
    print(f"• History Messages: {len(coordinator.chat_history)}")
    print(f"• Telegram Bot    : {bot_status}")
    if allowed:
        print(f"• Authorized Users: {allowed}")
    print("─" * 56 + "\n")


def main():
    print(BANNER)

    logging.basicConfig(
        format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
        level=logging.WARNING,
    )

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    raw_allowed_ids = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
    allowed_ids = [int(i.strip()) for i in raw_allowed_ids.split(",") if i.strip().isdigit()]

    orchestrator = ApplicationOrchestrator()

    # 1. Check for interrupted task or saved session
    interrupted = check_interrupted_checkpoint(orchestrator)
    chat_history = []
    working_memory = {}
    completed_tasks = {}

    if interrupted:
        session_id = f"remote_{uuid.uuid4().hex[:8]}"
        working_memory = interrupted.get("working_memory", {})
        completed_tasks = interrupted.get("completed_tasks", {})
        chat_history = interrupted.get("chat_history", [])
    else:
        chat_history, working_memory, completed_tasks = check_saved_session(orchestrator)
        session_id = f"remote_{uuid.uuid4().hex[:8]}"

    # 2. Instantiate RemoteControlCoordinator
    coordinator = RemoteControlCoordinator(
        orchestrator=orchestrator,
        session_id=session_id,
        chat_history=chat_history,
        working_memory=working_memory,
        completed_tasks=completed_tasks,
    )

    # 3. Setup listener for active source shifting (Rule 1)
    def on_source_shift(old_src: str, new_src: str):
        if new_src == "telegram":
            print(f"\n[Remote Control] 📲 Active conversation shifted to Telegram. Continuing in shared session...")
        elif new_src == "cli":
            print(f"\n[Remote Control] 🖥️ Active conversation shifted to CLI.")

    coordinator.register_shift_listener(on_source_shift)

    # 4. Start background Telegram bot if configured
    if token:
        try:
            print("🚀 Launching background Telegram Gateway...")
            coordinator.start_telegram_background(token=token, allowed_user_ids=allowed_ids)
            print("✔ Telegram Gateway active in background.")
            if allowed_ids:
                print(f"🔒 Whitelist: {len(allowed_ids)} authorized User ID(s).")
        except Exception as tg_err:
            print(f"⚠️ Could not start background Telegram adapter: {tg_err}")
    else:
        print("⚠️ Notice: TELEGRAM_BOT_TOKEN not configured in .env.")
        print("   Running in CLI mode. Add your token to .env to enable dual-mode Telegram interaction.\n")

    print(f"• Active Shared Session: {coordinator.session_id}")
    print("• Type your query or '/help' for commands, 'exit' to quit.\n")

    verbose = False

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

                if user_input.startswith("/export"):
                    cmd_args = user_input[len("/export"):].strip()
                    handle_export_command(coordinator, cmd_args)
                    continue

                if user_input.startswith("/status") or user_input.startswith("/remote") or user_input.startswith("/remote_control"):
                    cmd_part = user_input.split(maxsplit=1)
                    subcmd = cmd_part[1].lower() if len(cmd_part) > 1 else ""
                    if subcmd in ("stop", "off"):
                        coordinator.stop()
                        print("\n🛑 Telegram Gateway stopped.\n")
                    elif subcmd in ("start", "on"):
                        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
                        coordinator.start_telegram_background(token=token, allowed_user_ids=allowed_ids)
                        print("\n🚀 Telegram Gateway started in background.\n")
                    else:
                        print_remote_status(coordinator)
                    continue

                if user_input == "/verbose":
                    verbose = not verbose
                    print(f"\nLive Verbose Logs are now: {'ON' if verbose else 'OFF'}\n")
                    continue

                if user_input == "/history":
                    if not coordinator.chat_history:
                        print("\nNo previous turns in this conversation yet.\n")
                    else:
                        print(f"\n📜 Shared Conversation History ({len(coordinator.chat_history)} messages):")
                        for msg in coordinator.chat_history:
                            src = f" [{msg.get('source', '').upper()}]" if msg.get("source") else ""
                            role_symbol = f"🧑 You{src}" if msg["role"] == "user" else "🤖 Assistant"
                            print(f"  {role_symbol}: {msg['content'][:120]}...")
                        print()
                    continue

                if user_input == "/session":
                    print(f"\nCurrent Shared Session ID: {coordinator.session_id}\n")
                    continue

                if user_input == "/workers":
                    print("\n📦 Registered Modular Workers:")
                    for w in orchestrator.workers:
                        print(f"  • {w.name:<22} [{', '.join(w.categories)}]")
                    print()
                    continue

                if user_input == "/new":
                    coordinator.session_id = f"remote_{uuid.uuid4().hex[:8]}"
                    coordinator.chat_history.clear()
                    coordinator.working_memory.clear()
                    coordinator.completed_tasks.clear()
                    coordinator.turns.clear()
                    orchestrator.clear_saved_session()
                    orchestrator.clear_interrupted_checkpoint()
                    print(f"\nStarted new shared session: {coordinator.session_id} (context cleared)\n")
                    continue

                if not verbose:
                    print("\n⏳ Processing request through router, scheduler & workers...")
                else:
                    print("\n⏳ Executing pipeline stream:")

                # Execute query through coordinator in thread-safe shared session
                response = coordinator.execute_query(
                    user_prompt=user_input,
                    source="cli",
                    verbose=verbose,
                )
                print(f"\n🤖 Assistant:\n{response}\n")

            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
    finally:
        print("🛑 Shutting down Remote Control session...")
        coordinator.stop()


if __name__ == "__main__":
    main()
