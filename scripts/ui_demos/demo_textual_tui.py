"""
Demo 1: Textual Full-Screen TUI Dashboard
Run with: python scripts/ui_demos/demo_textual_tui.py
"""
import asyncio
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Input, Static, Label, Button, Tree, ProgressBar, Rule
from textual.reactive import reactive
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

CSS = """
Screen {
    background: #0d1117;
    color: #c9d1d9;
}

#main-container {
    height: 1fr;
    width: 1fr;
}

#chat-pane {
    width: 68%;
    height: 100%;
    border-right: solid #30363d;
    padding: 1;
}

#sidebar-pane {
    width: 32%;
    height: 100%;
    background: #161b22;
    padding: 1;
}

#chat-scroll {
    height: 1fr;
    border: round #30363d;
    background: #0d1117;
    padding: 1;
}

.chat-bubble {
    margin: 1 0;
    padding: 1;
    background: #1f242c;
    border-left: wide #58a6ff;
}

.user-bubble {
    margin: 1 0;
    padding: 1;
    background: #162a3f;
    border-left: wide #1f6feb;
}

.tool-bubble {
    margin: 1 0;
    padding: 1;
    background: #251d14;
    border-left: wide #d29922;
    color: #e3b341;
}

#input-box {
    margin-top: 1;
    border: tall #58a6ff;
    background: #161b22;
}

.section-title {
    color: #58a6ff;
    text-style: bold;
    margin-bottom: 1;
}

.stat-row {
    margin: 0 0 1 0;
    color: #8b949e;
}

.stat-val {
    color: #7ee787;
    text-style: bold;
}

.worker-active {
    color: #7ee787;
}

.worker-idle {
    color: #8b949e;
}
"""

class ChatMessage(Static):
    pass

class AssistantTUIDemo(App):
    CSS = CSS
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "clear_chat", "Clear Screen"),
        ("f1", "help", "Help"),
    ]

    tokens_used = reactive(1420)
    current_worker = reactive("Idle")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            # Left: Chat & Workflow
            with Vertical(id="chat-pane"):
                with VerticalScroll(id="chat-scroll"):
                    yield ChatMessage(
                        Markdown("### 🤖 **AI Assistant Dashboard Initialized**\n*Type a prompt below (e.g. `check emails`, `research AI papers`, or anything) to see the live agent reactive flow.*"),
                        classes="chat-bubble"
                    )
                yield Input(placeholder="💬 Ask your assistant anything (or try 'check emails', 'search arxiv')...", id="input-box")

            # Right: Real-time System / Memory / Worker Inspector
            with Vertical(id="sidebar-pane"):
                yield Label("⚡ AGENT INTROSPECTION", classes="section-title")
                yield Static("Active Worker: [bold green]StateGraph Router[/bold green]", id="active-worker-status")
                yield Static("Active State: [bold cyan]Awaiting Input[/bold cyan]", id="active-state-status")
                yield Rule()

                yield Label("🧠 MEMORY & GRAPH STATE", classes="section-title")
                yield Static("• Vector Memory: [green]Ready (48 docs)[/green]")
                yield Static("• Working Context: [cyan]2.1k / 32k tokens[/cyan]")
                yield Static("• Active Skills: [yellow]gmail, research, browser[/yellow]")
                yield Rule()

                yield Label("🛠️ WORKER FLEET", classes="section-title")
                yield Static("🟢 [bold]Orchestrator[/bold] - Ready")
                yield Static("⚪ [bold]GmailWorker[/bold] - Standby (IMAP Idle)")
                yield Static("⚪ [bold]ResearchWorker[/bold] - Standby")
                yield Static("⚪ [bold]BrowserWorker[/bold] - Headless Ready")
                yield Rule()

                yield Label("📊 SESSION METRICS", classes="section-title")
                yield Static("Total Tokens: [bold green]1,420[/bold green]")
                yield Static("Latency (Last Tool): [bold cyan]240ms[/bold cyan]")
                yield Static("Confidence Guard: [bold green]PASS (0.94)[/bold green]")
        
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        event.input.value = ""
        chat_scroll = self.query_one("#chat-scroll", VerticalScroll)

        # 1. User Bubble
        await chat_scroll.mount(ChatMessage(Markdown(f"**You:** {user_text}"), classes="user-bubble"))
        chat_scroll.scroll_end(animate=True)

        # 2. Simulate Router & Tool execution
        worker_label = self.query_one("#active-worker-status", Static)
        state_label = self.query_one("#active-state-status", Static)

        worker_label.update("Active Worker: [bold yellow]TaskRouter[/bold yellow]")
        state_label.update("Active State: [bold yellow]Planning Workflow...[/bold yellow]")

        # Tool step 1
        await asyncio.sleep(0.6)
        await chat_scroll.mount(ChatMessage(
            Markdown("⚙️ **[Router]** Classified Intent -> `GmailWorker` & `VectorMemoryLookup`"),
            classes="tool-bubble"
        ))
        chat_scroll.scroll_end(animate=True)
        worker_label.update("Active Worker: [bold green]GmailWorker[/bold green]")

        # Tool step 2
        await asyncio.sleep(0.8)
        await chat_scroll.mount(ChatMessage(
            Markdown("🔍 **[Memory]** Recalled user preference: *'Prefers daily email digests formatted with bullet points'* (score: 0.91)"),
            classes="tool-bubble"
        ))
        chat_scroll.scroll_end(animate=True)

        # Assistant Response Stream
        await asyncio.sleep(0.7)
        resp_widget = ChatMessage(Markdown("🤖 **Assistant:**\n\nI checked your mailbox. You have **3 unread emails**:\n\n1. **GitHub Alert**: Security advisory on `urllib3` (Low priority)\n2. **Meeting Invite**: Weekly Sync at 3:00 PM tomorrow\n3. **Newsletter**: Morning AI Digest #42\n\nWould you like me to draft replies or summarize the GitHub alert?"), classes="chat-bubble")
        await chat_scroll.mount(resp_widget)
        chat_scroll.scroll_end(animate=True)

        worker_label.update("Active Worker: [bold green]Idle[/bold green]")
        state_label.update("Active State: [bold cyan]Awaiting Input[/bold cyan]")

    def action_clear_chat(self) -> None:
        chat_scroll = self.query_one("#chat-scroll", VerticalScroll)
        chat_scroll.remove_children()

if __name__ == "__main__":
    app = AssistantTUIDemo()
    app.run()
