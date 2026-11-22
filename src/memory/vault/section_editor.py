"""Pure text parsing and section-bounded edits for Markdown documents."""

from __future__ import annotations

import re
from typing import Optional, Tuple


def extract_section(content: str, section_name: str) -> str:
    """Extracts lines belonging exclusively to a section header."""
    pattern = re.compile(
        rf"^##\s+{re.escape(section_name.strip())}\s*$(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(content)
    return match.group(1).strip() if match else f"Section '## {section_name}' not found."


def filter_lines_by_query(content: str, query: str, filename: str) -> str:
    """Filters lines in content by query string."""
    clean_q = query.strip().lower()
    matches = [line for line in content.splitlines() if clean_q in line.lower()]
    return "\n".join(matches) if matches else f"No matches found for '{query}' in '{filename}'."


def format_bullet_entry(entry_content: str) -> str:
    """Ensures entry text is formatted as a clean markdown bullet."""
    clean = entry_content.strip()
    return clean if clean.startswith(("- ", "* ")) else f"- {clean}"


def upsert_section_entry(
    text: str,
    section: str,
    entry_content: str,
    key: Optional[str] = None,
) -> Tuple[str, str]:
    """Inserts or replaces an entry inside a section block while preserving surrounding format."""
    clean_entry = format_bullet_entry(entry_content)
    sec_pattern = re.compile(
        rf"(^##\s+{re.escape(section.strip())}\s*$)(\n.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    match = sec_pattern.search(text)

    if not match:
        separator = "\n\n" if text.strip() else ""
        new_section = f"{separator}## {section.strip()}\n{clean_entry}\n"
        return text + new_section, "created section and entry"

    sec_body = match.group(2)
    match_key = (key or "").strip().lower()

    if match_key:
        lines = sec_body.splitlines()
        for idx, line in enumerate(lines):
            if match_key in line.lower() and line.strip().startswith(("-", "*")):
                lines[idx] = clean_entry
                updated_body = "\n".join(lines) + ("\n" if sec_body.endswith("\n") else "")
                return text[: match.start(2)] + updated_body + text[match.end(2) :], "updated entry"

    trimmed_body = sec_body.rstrip()
    updated_body = f"{trimmed_body}\n{clean_entry}\n\n"
    return text[: match.start(2)] + updated_body + text[match.end(2) :], "added entry"


def delete_section_entry(text: str, section: str, key: str) -> Tuple[str, bool]:
    """Deletes a matching line inside a section block."""
    sec_pattern = re.compile(
        rf"(^##\s+{re.escape(section.strip())}\s*$)(\n.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    match = sec_pattern.search(text)
    if not match:
        return text, False

    clean_key = key.strip().lower()
    lines = match.group(2).splitlines()
    filtered = [
        line
        for line in lines
        if not (clean_key in line.lower() and line.strip().startswith(("-", "*")))
    ]

    if len(filtered) == len(lines):
        return text, False

    updated_body = "\n".join(filtered) + ("\n" if match.group(2).endswith("\n") else "")
    return text[: match.start(2)] + updated_body + text[match.end(2) :], True
