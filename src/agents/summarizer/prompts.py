"""Prompt loader for SummarizerAgent."""

from pathlib import Path

DEFAULT_SUMMARIZER_PROMPT = (
    "You are the Summarizer Specialist Agent. "
    "Synthesize user goals and subtask execution outputs into a clean, "
    "well-structured, and human-readable response without conversational filler."
)


def get_summarizer_prompt() -> str:
    """Loads system prompt from local prompt.md or returns default fallback."""
    prompt_file = Path(__file__).parent / "prompt.md"
    if prompt_file.is_file():
        content = prompt_file.read_text(encoding="utf-8").strip()
        if content:
            return content
    return DEFAULT_SUMMARIZER_PROMPT
