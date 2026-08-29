"""
Artistic Claude-Code-Style CLI for AI Personal Assistant
Run with: .venv/bin/python scripts/ui_demos/demo_pro_cli.py
"""
import sys
import time
import os
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import FormattedText
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.live import Live
from rich.text import Text
from rich.syntax import Syntax
from rich.spinner import Spinner
from rich.columns import Columns

console = Console(highlight=False)

# Custom color palette (Claude / Anthropic warm obsidian & terracotta + emerald tones)
CLAUDE_ORANGE = "#D97706"
ACCENT_CYAN = "#38BDF8"
ACCENT_PURPLE = "#A855F7"
ACCENT_GREEN = "#34D399"
DIM_GRAY = "#64748B"
TEXT_LIGHT = "#F8FAFC"
BG_DARK = "#0F172A"

pt_style = Style.from_dict({
    'prompt': '#D97706 bold',
    'symbol': '#F59E0B bold',
    'bottom-toolbar': '#94a3b8 bg:#0f172a',
    'bottom-toolbar.key': '#38bdf8 bold',
    'bottom-toolbar.val': '#f8fafc',
})

commands_completer = WordCompleter([
    '/help', '/memory', '/workers', '/skills', '/stats', '/clear', '/cost', '/exit',
    '/doctor', '/graph', 'check unread emails', 'research agent architectures',
    'search vector memory for robotics notes'
], ignore_case=True)

def get_bottom_toolbar():
    return FormattedText([
        ('class:bottom-toolbar', ' '),
        ('class:bottom-toolbar.key', '✦ Model: '),
        ('class:bottom-toolbar.val', 'StateGraph+Gemini 2.5 '),
        ('class:bottom-toolbar', ' │ '),
        ('class:bottom-toolbar.key', 'Memory: '),
        ('class:bottom-toolbar.val', 'HNSW 48 docs '),
        ('class:bottom-toolbar', ' │ '),
        ('class:bottom-toolbar.key', 'Context: '),
        ('class:bottom-toolbar.val', '7.4% (2.4k/32k) '),
        ('class:bottom-toolbar', ' │ '),
        ('class:bottom-toolbar', 'Type '),
        ('class:bottom-toolbar.key', '/help'),
        ('class:bottom-toolbar', ' for shortcuts'),
    ])

def render_banner():
    console.print()
    banner_text = Text()
    banner_text.append("  ✦ ", style="bold #D97706")
    banner_text.append("PERSONAL ASSISTANT", style="bold #F8FAFC")
    banner_text.append("  v2.4.0", style="dim #64748B")
    banner_text.append("  •  ", style="dim #475569")
    banner_text.append("StateGraph Orchestrator", style="#38BDF8")
    banner_text.append("  •  ", style="dim #475569")
    banner_text.append("Linux (x86_64)", style="dim #64748B")
    
    console.print(banner_text)
    
    chips = Text()
    chips.append("  [Working Directory: ", style="dim #64748B")
    chips.append(os.path.basename(os.getcwd()), style="#94A3B8")
    chips.append("]  [Workers: ", style="dim #64748B")
    chips.append("4 Active", style="bold #34D399")
    chips.append("]  [Memory Guard: ", style="dim #64748B")
    chips.append("Enabled", style="bold #A855F7")
    chips.append("]", style="dim #64748B")
    console.print(chips)
    console.print(Text("  " + "─" * 68, style="dim #334155"))
    console.print()

def stream_markdown(text: str, delay: float = 0.008):
    """Simulates smooth token streaming with Rich Markdown."""
    words = text.split(" ")
    buffer = ""
    for word in words:
        buffer += word + " "
        # Print cleanly in place or stream
        time.sleep(delay)
    console.print(Markdown(text))

def render_tool_call(title: str, subtitle: str, lines: list, status_tag: str = "COMPLETED", duration: str = "0.34s"):
    t = Table.grid(padding=(0, 1))
    t.add_column(style="#64748B")
    t.add_column(style="#E2E8F0")

    for k, v in lines:
        t.add_row(f"{k}:", v)

    header = Text()
    header.append("╭─ ", style="dim #D97706")
    header.append("⚙ ", style="#F59E0B")
    header.append(f"{title} ", style="bold #F8FAFC")
    header.append(f"({subtitle}) ", style="dim #94A3B8")
    header.append("─" * max(4, (55 - len(title) - len(subtitle))), style="dim #D97706")
    
    console.print(header)
    for k, v in lines:
        console.print(Text(f"│  {k}: ", style="dim #64748B") + Text(f"{v}", style="#E2E8F0"))
    
    footer = Text()
    footer.append("╰─ ", style="dim #D97706")
    footer.append(f"✔ {status_tag} ", style="bold #34D399")
    footer.append(f"[{duration}] ", style="dim #64748B")
    footer.append("─" * 40, style="dim #D97706")
    console.print(footer)
    console.print()

def simulate_claude_execution(user_query: str):
    console.print()
    
    # 1. Subtle Thinking Pulse
    with console.status("[dim #94A3B8]● Thinking through StateGraph orchestrator...[/dim #94A3B8]", spinner="dots") as status:
        time.sleep(0.5)
        status.update("[dim #D97706]✦ Routing intent & querying Vector Memory...[/dim #D97706]")
        time.sleep(0.6)

    # 2. Tool Invocation Card 1 (Vector Memory)
    render_tool_call(
        title="VectorMemory.query",
        subtitle="semantic_search",
        lines=[
            ("Collection", "assistant_knowledge_base"),
            ("Query", f'"{user_query}"'),
            ("Context Found", "1 prior conversation rule ('Prefers concise action-oriented summaries')"),
            ("Confidence", "0.94 (Passes Guardrail)")
        ],
        status_tag="MATCHED",
        duration="142ms"
    )

    # 3. Tool Invocation Card 2 (Worker Execution)
    with console.status("[dim #38BDF8]✦ Executing Worker Tools (IMAP & Search)...[/dim #38BDF8]", spinner="aesthetic"):
        time.sleep(0.7)

    render_tool_call(
        title="GmailWorker.get_unread_emails",
        subtitle="inbox_scanner",
        lines=[
            ("Filter", "is:unread category:primary"),
            ("Messages", "3 new threads retrieved"),
            ("Top Sender", "GitHub Notifications <notifications@github.com>"),
            ("IMAP Daemon", "Listening (IDLE state active)")
        ],
        status_tag="FETCHED",
        duration="280ms"
    )

    # 4. Assistant Answer Header
    ans_header = Text()
    ans_header.append("✦ ", style="bold #D97706")
    ans_header.append("Assistant", style="bold #F8FAFC")
    ans_header.append("  (Gemini 2.5 Pro)", style="dim #64748B")
    console.print(ans_header)
    console.print()

    # 5. Formatted Markdown Response
    response_body = f"""I scanned your notifications and contextualized them with your working memory:

* **📬 Unread Emails (3)**
  * **[GitHub]** Security alert on dependency `aiohttp` in repo `personal-assistant-v2`.
  * **[Calendar]** Sync with Core Team scheduled for tomorrow at **11:00 AM**.
  * **[Newsletter]** *Deep Learning Weekly #312* (Transformer architecture improvements).

* **💡 Suggested Next Steps**
  1. Draft a quick confirmation for tomorrow's sync.
  2. Inspect the `aiohttp` security advisory.
"""
    stream_markdown(response_body, delay=0.005)
    
    # 6. Subtle execution footer chips
    footer_stats = Text()
    footer_stats.append("  ", style="")
    footer_stats.append("Tokens: ", style="dim #64748B")
    footer_stats.append("482 in / 178 out", style="#94A3B8")
    footer_stats.append("  •  ", style="dim #475569")
    footer_stats.append("Latency: ", style="dim #64748B")
    footer_stats.append("1.12s", style="#34D399")
    footer_stats.append("  •  ", style="dim #475569")
    footer_stats.append("Cost: ", style="dim #64748B")
    footer_stats.append("~$0.0008", style="#94A3B8")
    console.print(footer_stats)
    console.print(Text("  " + "─" * 68, style="dim #1E293B"))
    console.print()

def main():
    console.clear()
    render_banner()
    
    session = PromptSession(
        history=InMemoryHistory(),
        completer=commands_completer,
        style=pt_style
    )

    while True:
        try:
            user_input = session.prompt(
                FormattedText([
                    ('class:symbol', '❯ '),
                ]),
                bottom_toolbar=get_bottom_toolbar
            ).strip()

            if not user_input:
                continue

            if user_input.lower() in ['/exit', 'exit', 'quit', '/quit']:
                console.print(Text("\n✦ Shutting down assistant backend gracefully. Goodbye!\n", style="bold #D97706"))
                break

            elif user_input.lower() == '/clear':
                console.clear()
                render_banner()

            elif user_input.lower() == '/help':
                console.print()
                t = Table(title="✦ Available Slash Commands", border_style="dim #334155", header_style="bold #38BDF8")
                t.add_column("Command", style="bold #F59E0B", no_wrap=True)
                t.add_column("Description", style="#E2E8F0")
                t.add_row("/workers", "Inspect status of Gmail, Browser, Research & Music workers")
                t.add_row("/memory", "Inspect Vector Memory collection & HNSW index health")
                t.add_row("/graph", "Display StateGraph execution routes & active nodes")
                t.add_row("/stats", "Detailed breakdown of tokens, latency, and session cost")
                t.add_row("/clear", "Clear the screen and re-render the status banner")
                t.add_row("/exit", "Exit session")
                console.print(t)
                console.print()

            elif user_input.lower() == '/workers':
                console.print()
                t = Table(title="✦ Worker Subsystem Status", border_style="dim #334155", header_style="bold #38BDF8")
                t.add_column("Worker", style="bold #F8FAFC")
                t.add_column("State", style="#34D399")
                t.add_column("Transport / Engine", style="#94A3B8")
                t.add_column("Details", style="#E2E8F0")
                t.add_row("GmailWorker", "● ACTIVE", "IMAP + OAuth2", "Listening for background incoming mail")
                t.add_row("BrowserWorker", "● READY", "Playwright Headless", "Isolated sandbox with DOM tagging")
                t.add_row("ResearchWorker", "● READY", "ArXiv + OpenAlex + DDG", "Autonomous synthesis pipeline")
                t.add_row("MusicWorker", "○ STANDBY", "YTMusic API", "Playback queue synced")
                console.print(t)
                console.print()

            elif user_input.lower() == '/memory':
                console.print()
                render_tool_call(
                    title="UnifiedMemory.stats",
                    subtitle="chroma_hnsw_inspector",
                    lines=[
                        ("Vector Store", "48 embedded document vectors"),
                        ("Knowledge Graph", "116 entity nodes, 214 relational edges"),
                        ("Cache Hit Ratio", "92.4% (Fast-path memory retrieval)"),
                        ("Embedding Model", "text-embedding-004 (768 dimensions)")
                    ],
                    status_tag="HEALTHY",
                    duration="12ms"
                )

            elif user_input.lower() == '/stats':
                console.print()
                t = Table(title="✦ Session Metrics", border_style="dim #334155", header_style="bold #38BDF8")
                t.add_column("Metric", style="#94A3B8")
                t.add_column("Value", style="bold #34D399")
                t.add_row("Prompts Submitted", "4")
                t.add_row("Total Tool Invocations", "8")
                t.add_row("Prompt Tokens", "3,120")
                t.add_row("Completion Tokens", "840")
                t.add_row("Estimated Cost", "$0.0016")
                console.print(t)
                console.print()

            else:
                simulate_claude_execution(user_input)

        except (KeyboardInterrupt, EOFError):
            console.print(Text("\n✦ Session aborted.\n", style="bold #D97706"))
            break

if __name__ == "__main__":
    main()
