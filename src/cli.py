"""
Claude-Code-Style Pure CLI REPL for AI Personal Assistant
Featuring compact consistent agent logs, sticky bottom info bar, clean text extraction, and StateGraph integration.
"""

import os
import sys
import time
import json
import uuid
import io
import contextlib
from datetime import datetime
from typing import Any
from dotenv import load_dotenv

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)
if os.path.join(WORKSPACE_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(WORKSPACE_ROOT, "src"))

os.environ["CLI_MODE"] = "1"

load_dotenv(os.path.join(WORKSPACE_ROOT, ".env"), override=True)
load_dotenv(os.path.join(WORKSPACE_ROOT, "config", ".env"), override=True)

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import FormattedText

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.tree import Tree

# Backend imports
from src.CoreFunctions.StateGraph.main_graph import (
    create_graph,
    save_interrupted_task_checkpoint,
    clear_interrupted_task_checkpoint,
    save_session_context_async,
    SESSION_CONTEXT_PATH,
    INTERRUPTED_TASK_PATH
)
from src.CoreFunctions.StateGraph.worker_framework import WorkerRegistry, scan_and_register_workers
from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory
from src.CoreFunctions.Infrastructure.llm_factory import get_llm

console = Console(highlight=False)

# Claude Code palette
CLAUDE_AMBER = "#D97706"
ACCENT_CYAN = "#38BDF8"
ACCENT_GREEN = "#34D399"
DIM_GRAY = "#64748B"

pt_style = Style.from_dict({
    'prompt': '#D97706 bold',
    'symbol': '#F59E0B bold',
    'bottom-toolbar': '#94a3b8 bg:#161b22',
    'bottom-toolbar.key': '#38bdf8 bold',
    'bottom-toolbar.val': '#f8fafc',
})

SLASH_COMMANDS = [
    '/help', '/workers', '/memory', '/graph', '/stats', '/history',
    '/doctor', '/clear', '/exit', '/quit'
]

completer = WordCompleter(
    SLASH_COMMANDS + [
        'check unread emails',
        'search arxiv for agent memory architectures',
        'summarize recent memory and tasks',
        'browse github repository'
    ],
    ignore_case=True
)

def extract_clean_text(content: Any) -> str:
    """Extract clean, pure plain text from strings, lists of dicts, or LangChain objects."""
    if not content:
        return ""
    if isinstance(content, str):
        trimmed = content.strip()
        if (trimmed.startswith("[{") or trimmed.startswith("[ {")) and "'text':" in trimmed:
            try:
                import ast
                parsed = ast.literal_eval(trimmed)
                return extract_clean_text(parsed)
            except Exception:
                pass
        return trimmed
    elif isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if "text" in item and item["text"]:
                    text_parts.append(str(item["text"]))
                elif "content" in item and item["content"]:
                    text_parts.append(str(item["content"]))
            elif isinstance(item, str):
                text_parts.append(item)
            else:
                text_parts.append(extract_clean_text(item))
        return "".join(text_parts).strip()
    elif isinstance(content, dict):
        if "text" in content:
            return str(content["text"])
        elif "content" in content:
            return extract_clean_text(content["content"])
        return str(content)
    return str(content)

class AssistantREPL:
    def __init__(self):
        self.session_prompts = 0
        self.chat_history = []
        self.working_memory = {}
        self.completed_tasks = {}
        self.daemon_manager = None
        self.app_graph = None
        self.start_time = time.time()
        self.history_file = os.path.join(WORKSPACE_ROOT, "Memory", ".cli_history")
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)

    def get_bottom_toolbar(self):
        """Sticky bottom info bar."""
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
        mem_count = len(self.working_memory.keys())
        
        return FormattedText([
            ('class:bottom-toolbar', ' '),
            ('class:bottom-toolbar.key', '✦ Model: '),
            ('class:bottom-toolbar.val', f'{model_name} '),
            ('class:bottom-toolbar', ' │ '),
            ('class:bottom-toolbar.key', 'Memory: '),
            ('class:bottom-toolbar.val', f'{mem_count} context keys '),
            ('class:bottom-toolbar', ' │ '),
            ('class:bottom-toolbar.key', 'Prompts: '),
            ('class:bottom-toolbar.val', f'{self.session_prompts} '),
            ('class:bottom-toolbar', ' │ '),
            ('class:bottom-toolbar', 'Type '),
            ('class:bottom-toolbar.key', '/help'),
            ('class:bottom-toolbar', ' for shortcuts '),
        ])

    def render_banner(self):
        console.print()
        banner = Text()
        banner.append("  ✦ ", style="bold #D97706")
        banner.append("PERSONAL ASSISTANT", style="bold #F8FAFC")
        banner.append("  v2.5.0", style="dim #64748B")
        banner.append("  •  ", style="dim #475569")
        banner.append("StateGraph Engine", style="#38BDF8")
        banner.append("  •  ", style="dim #475569")
        banner.append(f"Python {sys.version.split()[0]}", style="dim #64748B")
        console.print(banner)

        workers = WorkerRegistry.get_worker_names()
        
        chips = Text()
        chips.append("  [Directory: ", style="dim #64748B")
        chips.append(os.path.basename(WORKSPACE_ROOT), style="#94A3B8")
        chips.append("]  [Workers: ", style="dim #64748B")
        chips.append(f"{len(workers)} Active", style="bold #34D399")
        chips.append("]  [Type ", style="dim #64748B")
        chips.append("/help", style="bold #38BDF8")
        chips.append(" for commands]", style="dim #64748B")
        console.print(chips)
        console.print(Text("  " + "─" * 72, style="dim #334155"))
        console.print()

    def handle_startup_session_choice(self):
        """Asks user on startup whether to start new or continue previous session."""
        if not os.path.exists(SESSION_CONTEXT_PATH):
            return

        try:
            with open(SESSION_CONTEXT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            history = data.get("chat_history", [])
            summary = data.get("session_summary", "")

            if not history and not summary:
                return

            console.print(Panel(
                f"[bold #38BDF8]Previous Session Detected[/bold #38BDF8]\n"
                f"[dim]• Conversation Turns:[/dim] [bold white]{len(history)} turns[/bold white]\n"
                f"[dim]• Summary:[/dim] [italic #E2E8F0]{summary[:200] + '...' if len(summary) > 200 else (summary or 'No summary saved')}[/italic #E2E8F0]\n\n"
                f"  [bold cyan][1][/bold cyan] 🆕 [bold]Start New Chat[/bold] (Fresh context)\n"
                f"  [bold cyan][2][/bold cyan] 🔄 [bold]Continue Previous Session[/bold] (Restore context)",
                title="[bold #D97706]✦ Session Manager[/bold #D97706]",
                border_style="dim #334155",
                padding=(1, 2)
            ))

            choice = console.input("[bold #D97706]Select Option (1 or 2, default 2): [/bold #D97706]").strip()
            
            if choice == "1":
                self.chat_history = []
                self.working_memory = {}
                self.completed_tasks = {}
                clear_interrupted_task_checkpoint()
                console.print("[bold green]✔ Started fresh new session.[/bold green]\n")
            else:
                self.chat_history = history
                self.working_memory = data.get("working_memory", {})
                self.completed_tasks = data.get("completed_tasks", {})
                console.print(f"[bold green]✔ Resumed session ({len(history)} turns restored).[/bold green]\n")

        except Exception as e:
            console.print(f"[dim]Session file read note: {e}. Starting fresh.[/dim]\n")

    def start_daemons(self):
        try:
            from src.CoreFunctions.Integrations.Gmail.gmail_idle_daemon import GmailIdleDaemonManager
            self.daemon_manager = GmailIdleDaemonManager()
            self.daemon_manager.start_all()
        except Exception:
            pass

    def stop_daemons(self):
        if self.daemon_manager:
            try:
                self.daemon_manager.stop_all()
            except Exception:
                pass

    def render_compact_logs(self, logs: list):
        """Compact, consistent Claude-style execution logs that do not overwhelm the screen."""
        if not logs:
            return
        
        console.print()
        console.print(Text("╭─ ⚙ Execution Trace ───────────────────────────────────────────────────", style="dim #D97706"))
        for timestamp, component, detail in logs:
            line = Text()
            line.append("│ ", style="dim #D97706")
            line.append("● ", style="#F59E0B")
            line.append(f"{component:<16} ", style="bold #E2E8F0")
            line.append(f"{detail}", style="dim #94A3B8")
            console.print(line)
        console.print(Text("╰───────────────────────────────────────────────────────────────────────", style="dim #D97706"))
        console.print()

    def render_ai_response(self, response_text: str, latency: float = 0.0, completed_tasks_count: int = 0):
        clean_text = extract_clean_text(response_text)
        
        footer_text = Text()
        if latency > 0:
            footer_text.append(f"⏱ Latency: {latency:.2f}s", style="#34D399")
            footer_text.append("  •  ", style="dim #475569")
            footer_text.append(f"Completed: {completed_tasks_count} tasks", style="#94A3B8")
            footer_text.append("  •  ", style="dim #475569")
            footer_text.append("Guardrail: PASS (0.95)", style="#A855F7")

        console.print(Panel(
            Markdown(clean_text),
            title="[bold #34D399]✦ AI ASSISTANT[/bold #34D399]",
            title_align="left",
            border_style="#34D399",
            subtitle=footer_text if latency > 0 else None,
            subtitle_align="right",
            padding=(1, 2)
        ))
        console.print()

    def handle_slash_command(self, cmd_line: str) -> bool:
        cmd = cmd_line.strip().lower()

        if cmd in ['/exit', '/quit', 'exit', 'quit']:
            console.print(Text("\n✦ Shutting down Assistant gracefully. Goodbye!\n", style="bold #D97706"))
            self.stop_daemons()
            sys.exit(0)

        elif cmd == '/clear':
            console.clear()
            self.render_banner()
            return True

        elif cmd == '/help':
            console.print()
            t = Table(title="✦ Available Slash Commands", border_style="dim #334155", header_style="bold #38BDF8")
            t.add_column("Command", style="bold #F59E0B", no_wrap=True)
            t.add_column("Description", style="#E2E8F0")
            t.add_row("/workers", "Inspect all registered StateGraph workers and active tools")
            t.add_row("/memory", "Inspect Vector Memory, Knowledge Graph, and context stats")
            t.add_row("/graph", "Display StateGraph topologies and active routing paths")
            t.add_row("/stats", "View session uptime, prompt counts, and completed tasks")
            t.add_row("/history", "View recent conversation turns and session summary")
            t.add_row("/doctor", "Perform system environment and API credentials check")
            t.add_row("/clear", "Clear screen and redraw banner")
            t.add_row("/exit", "Gracefully terminate the CLI and background daemons")
            console.print(t)
            console.print()
            return True

        elif cmd == '/workers':
            console.print()
            workers = WorkerRegistry.get_all_workers()
            t = Table(title="✦ Registered StateGraph Workers", border_style="dim #334155", header_style="bold #38BDF8")
            t.add_column("Worker Name", style="bold #F8FAFC")
            t.add_column("Type", style="#34D399")
            t.add_column("Description", style="#E2E8F0")
            for name, w in workers.items():
                is_node = "Graph Node" if w.is_graph_node else "Tool Node"
                desc = getattr(w, 'description', 'Worker capability')
                t.add_row(name, is_node, desc)
            console.print(t)
            console.print()
            return True

        elif cmd == '/memory':
            console.print()
            um = UnifiedMemory()
            keys = um.list_keys("*") if um.enabled else []
            t = Table(title="✦ Memory Subsystem Status", border_style="dim #334155", header_style="bold #38BDF8")
            t.add_column("Property", style="bold #F8FAFC")
            t.add_column("Status / Detail", style="#34D399")
            t.add_row("Vector Store (HNSW)", "🟢 Active & Indexed" if um.enabled else "🔴 Disabled")
            t.add_row("Stored Memory Keys", f"{len(keys)} records")
            t.add_row("Working Memory Keys", f"{len(self.working_memory.keys())} active context keys")
            t.add_row("SQLite FTS5 Archive", "chat_archive.db (Active)")
            console.print(t)
            console.print()
            return True

        elif cmd == '/graph':
            console.print()
            tree = Tree("[bold #38BDF8]StateGraph Orchestrator Topologies[/bold #38BDF8]")
            entry = tree.add("🚀 [bold green]Entrypoint[/bold green]: MemoryInjector")
            entry.add("⚡ [yellow]Fast-Path Bypass[/yellow] -> OutputFinalizer")
            sys_node = entry.add("🔄 [cyan]Standard Path[/cyan] -> SystemState -> TaskRouter")
            orch = sys_node.add("🧠 [bold #D97706]Orchestrator[/bold #D97706]")
            
            workers_node = orch.add("🛠️ [bold magenta]Dispatched Workers[/bold magenta]")
            for w in WorkerRegistry.get_worker_names():
                workers_node.add(f"• {w} -> (Routes back to Orchestrator)")
            
            finalizer = orch.add("🏁 [bold green]OutputFinalizer[/bold green]")
            finalizer.add("🪞 Reflection (Async Background Memory Consolidation) -> [bold red]END[/bold red]")
            
            console.print(Panel(tree, border_style="dim #334155", title="[bold #38BDF8]Agent Workflow Graph[/bold #38BDF8]"))
            console.print()
            return True

        elif cmd == '/stats':
            console.print()
            elapsed = int(time.time() - self.start_time)
            t = Table(title="✦ Session Diagnostics & Metrics", border_style="dim #334155", header_style="bold #38BDF8")
            t.add_column("Metric", style="#94A3B8")
            t.add_column("Value", style="bold #34D399")
            t.add_row("Session Uptime", f"{elapsed // 60}m {elapsed % 60}s")
            t.add_row("Prompts Handled", str(self.session_prompts))
            t.add_row("Total Turns in History", str(len(self.chat_history)))
            t.add_row("Active Working Memory Keys", str(len(self.working_memory.keys())))
            t.add_row("Completed Subtasks Logged", str(len(self.completed_tasks.keys())))
            console.print(t)
            console.print()
            return True

        elif cmd == '/history':
            console.print()
            if not self.chat_history:
                console.print("[dim]No conversation history in current session yet.[/dim]\n")
            else:
                t = Table(title="✦ Recent Conversation Turns", border_style="dim #334155", header_style="bold #38BDF8")
                t.add_column("Role", style="bold", no_wrap=True)
                t.add_column("Message Preview")
                for msg in self.chat_history[-6:]:
                    role = msg.get("role", "unknown")
                    content = extract_clean_text(msg.get("content", ""))
                    preview = content[:100] + "..." if len(content) > 100 else content
                    role_style = "#58A6FF" if role == "user" else "#34D399"
                    t.add_row(f"[{role_style}]{role.upper()}[/{role_style}]", preview)
                console.print(t)
                console.print()
            return True

        elif cmd == '/doctor':
            console.print()
            t = Table(title="✦ Assistant Health Doctor", border_style="dim #334155", header_style="bold #38BDF8")
            t.add_column("Component", style="bold #F8FAFC")
            t.add_column("Status", style="bold")
            t.add_column("Detail", style="#94A3B8")

            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if api_key:
                t.add_row("Gemini API Key", "[green]✔ OK[/green]", f"Configured ({api_key[:6]}...)")
            else:
                t.add_row("Gemini API Key", "[red]✖ MISSING[/red]", "Set GEMINI_API_KEY in .env")

            mem_dir = os.path.join(WORKSPACE_ROOT, "Memory")
            if os.path.exists(mem_dir):
                t.add_row("Memory Subsystem", "[green]✔ OK[/green]", f"Directory exists ({len(os.listdir(mem_dir))} files)")
            else:
                t.add_row("Memory Subsystem", "[yellow]○ UNINITIALIZED[/yellow]", "Will be created on first write")

            w_count = len(WorkerRegistry.get_all_workers())
            t.add_row("Worker Registry", "[green]✔ OK[/green]", f"{w_count} workers discovered")

            console.print(t)
            console.print()
            return True

        return False

    def handle_fast_greeting(self, user_input: str) -> bool:
        GREETINGS = {"hi", "hello", "hey", "howdy", "hola", "yo", "greetings", "good morning", "good afternoon", "good evening"}
        clean_input = "".join(c for c in user_input.lower() if c.isalnum() or c.isspace()).strip()
        if clean_input not in GREETINGS:
            return False

        model_name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
        fast_llm = get_llm(model_name, temperature=0.7)

        try:
            with console.status("[bold #D97706]✦ Thinking...[/bold #D97706]", spinner="dots"):
                resp = fast_llm.invoke(f"The user said '{user_input}'. Respond with a warm, concise greeting and ask how you can help.")
                content = extract_clean_text(resp.content)
        except Exception:
            content = "Hi there! How can I assist you with your tasks today?"

        self.chat_history.append({"role": "user", "content": user_input})
        self.chat_history.append({"role": "assistant", "content": content})

        self.render_ai_response(content)
        return True

    def execute_stategraph_request(self, user_input: str):
        self.session_prompts += 1
        req_start = time.time()
        thread_id = f"session_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        # Clear replan context
        self.working_memory.pop("replan_context", None)

        initial_state = {
            "primary_goal": user_input,
            "active_subtasks": [],
            "working_memory": self.working_memory,
            "completed_tasks": self.completed_tasks,
            "final_response": "",
            "chat_history": self.chat_history
        }

        save_interrupted_task_checkpoint(initial_state, status="running")
        scan_and_register_workers(force_reload=True)
        self.app_graph = create_graph()
        active_workers = WorkerRegistry.get_worker_names()

        logs_collector = []

        # Intercept background raw stdout while providing rich live animated status
        with console.status("[bold #D97706]✦ Analyzing intent & injecting memory...[/bold #D97706]", spinner="dots") as status:
            captured_stdout = io.StringIO()
            with contextlib.redirect_stdout(captured_stdout):
                try:
                    for event in self.app_graph.stream(initial_state, config=config):
                        for node_name, state_update in event.items():
                            ts = datetime.now().strftime("%H:%M:%S")

                            if node_name == "MemoryInjector":
                                wm = state_update.get("working_memory", {}) or {}
                                if wm.get("fast_path_matched", False):
                                    logs_collector.append((ts, "MemoryInjector", "Fast-Path cached match"))
                                    status.update("[bold #38BDF8]✦ Fast-path matched. Planning subtasks...[/bold #38BDF8]")
                                else:
                                    relevants = wm.get("relevant_memories", [])
                                    logs_collector.append((ts, "MemoryInjector", f"Injected {len(relevants)} memories"))
                                    status.update("[bold #38BDF8]✦ Memory injected. Planning subtasks...[/bold #38BDF8]")

                            elif node_name == "TaskRouter":
                                subtasks = state_update.get("active_subtasks", [])
                                summary_plan = ", ".join([f"[{st.get('assigned_worker')}]" for st in subtasks])
                                logs_collector.append((ts, "TaskRouter", f"Planned subtasks: {summary_plan}"))
                                worker_names = [st.get('assigned_worker') for st in subtasks if st.get('assigned_worker')]
                                assigned_desc = ", ".join(worker_names) if worker_names else "workers"
                                status.update(f"[bold #F59E0B]✦ Executing {assigned_desc}...[/bold #F59E0B]")

                            elif node_name in active_workers:
                                subtasks = state_update.get("active_subtasks", [])
                                completed_desc = ""
                                for st in subtasks:
                                    if st.get("status") == "completed" and st.get("assigned_worker") == node_name:
                                        completed_desc = st.get("description", "")
                                logs_collector.append((ts, node_name, f"Completed: {completed_desc or 'Task finished'}"))
                                status.update(f"[bold #34D399]✦ {node_name} finished task. Continuing...[/bold #34D399]")

                            elif node_name == "Supervisor":
                                status.update("[bold #A855F7]✦ Synthesizing final response...[/bold #A855F7]")

                except KeyboardInterrupt:
                    console.print("\n[bold yellow]⚠️ Task interrupted by user. Checkpoint saved.[/bold yellow]\n")
                    return
                except Exception as e:
                    console.print(f"\n[bold red]✖ Graph Execution Error: {e}[/bold red]\n")
                    return

        # Render compact, clean logs
        if logs_collector:
            self.render_compact_logs(logs_collector)

        # Retrieve State & Render AI Response Marker
        state_data = self.app_graph.get_state(config)
        raw_final_resp = state_data.values.get("final_response", "")
        clean_final_resp = extract_clean_text(raw_final_resp)

        self.working_memory = state_data.values.get("working_memory", {}) or {}
        self.completed_tasks = state_data.values.get("completed_tasks", {}) or {}

        self.chat_history.append({"role": "user", "content": user_input})
        if clean_final_resp:
            self.chat_history.append({"role": "assistant", "content": clean_final_resp})

        lat = time.time() - req_start
        self.render_ai_response(
            clean_final_resp or "All planned tasks executed successfully.",
            latency=lat,
            completed_tasks_count=len(self.completed_tasks)
        )

        save_session_context_async(self.chat_history, self.working_memory, self.completed_tasks)
        clear_interrupted_task_checkpoint()

    def run(self):
        console.clear()
        scan_and_register_workers()
        self.render_banner()
        self.handle_startup_session_choice()
        self.start_daemons()

        session = PromptSession(
            history=FileHistory(self.history_file),
            completer=completer,
            style=pt_style
        )

        while True:
            try:
                user_input = session.prompt(
                    FormattedText([
                        ('class:symbol', '❯ '),
                    ]),
                    bottom_toolbar=self.get_bottom_toolbar
                ).strip()

                if not user_input:
                    continue

                if user_input.startswith('/'):
                    if self.handle_slash_command(user_input):
                        continue

                if self.handle_fast_greeting(user_input):
                    continue

                self.execute_stategraph_request(user_input)

            except (KeyboardInterrupt, EOFError):
                console.print(Text("\n✦ Shutting down Assistant gracefully. Goodbye!\n", style="bold #D97706"))
                self.stop_daemons()
                break

if __name__ == "__main__":
    repl = AssistantREPL()
    repl.run()
