"""Parser and AST representation for markdown profile sections."""

from collections import OrderedDict
from typing import List, Optional, Tuple


class SectionBlock:
    """Internal block maintaining raw lines and structured entries for non-destructive edits."""

    def __init__(self, title: str) -> None:
        self.title = title
        self.raw_lines: List[str] = []

    def get_entries(self) -> OrderedDict[str, str]:
        """Extracts key-value pairs from lines beginning with '- '."""
        entries: OrderedDict[str, str] = OrderedDict()
        for line in self.raw_lines:
            stripped = line.strip()
            if stripped.startswith("- "):
                item = stripped[2:].strip()
                if ":" in item:
                    k, v = item.split(":", 1)
                    entries[k.strip()] = v.strip()
                else:
                    entries[item] = ""
        return entries

    def set_entry(self, key: str, value: str) -> Tuple[bool, str]:
        """Sets or appends an entry. Returns (is_updated, canonical_key)."""
        clean_key = key.strip()
        clean_value = value.strip()
        new_line = f"- {clean_key}: {clean_value}" if clean_value else f"- {clean_key}:"

        for idx, line in enumerate(self.raw_lines):
            stripped = line.strip()
            if stripped.startswith("- "):
                item = stripped[2:].strip()
                existing_k = item.split(":", 1)[0].strip() if ":" in item else item.strip()
                if existing_k.lower() == clean_key.lower():
                    canonical_key = existing_k
                    self.raw_lines[idx] = (
                        f"- {canonical_key}: {clean_value}" if clean_value else f"- {canonical_key}:"
                    )
                    return (True, canonical_key)

        self.raw_lines.append(new_line)
        return (False, clean_key)

    def delete_entry(self, key: str) -> Optional[str]:
        """Deletes an entry by key case-insensitively. Returns deleted canonical key if found."""
        clean_key = key.strip().lower()
        for idx, line in enumerate(self.raw_lines):
            stripped = line.strip()
            if stripped.startswith("- "):
                item = stripped[2:].strip()
                existing_k = item.split(":", 1)[0].strip() if ":" in item else item.strip()
                if existing_k.lower() == clean_key:
                    del self.raw_lines[idx]
                    return existing_k
        return None
