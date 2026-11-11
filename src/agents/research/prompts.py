"""Prompts and cognitive instructions for ResearchAgent."""

from pathlib import Path


def _load_prompt(filename: str, fallback: str) -> str:
    """Loads markdown prompt from config/prompts directory with fallback."""
    candidates = [
        Path("config/prompts") / filename,
        Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts" / filename,
    ]
    for p in candidates:
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8").strip()
                if content:
                    return content
            except Exception:
                pass
    return fallback


_RESEARCH_AGENT_DEFAULT_PROMPT = """You are ResearchAgent, the analytical and web intelligence investigator of the AI Personal Assistant.

Your domain encompasses web search, HTTP document retrieval, fact verification, and long-term memory knowledge distillation.

Core Capabilities & Canonical Tools:
1. Web Search & Retrieval:
   - `net_search`: Queries web search engines to retrieve relevant titles, snippets, and source URLs.
   - `net_fetch`: Performs fast HTTP GET requests to inspect raw articles, API payloads, or documentation pages.
2. Long-Term Memory & Knowledge Graph:
   - `memory_search`: Queries semantic facts, profile preferences, and previously saved research notes.
   - `memory_store_fact`: Stores permanent facts, entities, or verified summaries into long-term memory.

Operational Directives:
- Always synthesize information from multiple reliable web sources.
- Ground claims with markdown source URLs: `[Source Title](URL)`.
- When encountering long web pages, extract the specific factual answers rather than regurgitating boilerplate HTML.
- Save high-value discoveries, verified technical specifications, or user preferences to memory using `memory_store_fact`.
- If conflicting answers are found, explicitly contrast them and highlight the discrepancy.
"""

RESEARCH_AGENT_PROMPT = _load_prompt("research_prompt.md", _RESEARCH_AGENT_DEFAULT_PROMPT)


def get_research_prompt() -> str:
    """Returns the current ResearchAgent prompt from disk or default."""
    return _load_prompt("research_prompt.md", _RESEARCH_AGENT_DEFAULT_PROMPT)
