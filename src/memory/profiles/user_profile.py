"""User Profile Manager for Core Profile and Personality/Tone Rules."""

import os
from collections import OrderedDict
from typing import Dict, List, Optional

from src.memory.profiles.atomic_file import atomic_write_text
from src.memory.profiles.markdown_profile_parser import SectionBlock

DEFAULT_CORE_PROFILE = """# User Core Profile

## Identity
- Name:
- Timezone:
- Primary OS:

## Preferences and Rules
- Tone: Technical, direct, concise, anti-slop.
- Communication: Direct answers, high information density.
"""


class UserProfileManager:
    """Manages reading, non-destructive updating, and serializing core_profile.md."""

    def __init__(self, file_path: str) -> None:
        self.file_path = os.path.abspath(os.path.expanduser(file_path))
        self._section_blocks: OrderedDict[str, SectionBlock] = OrderedDict()
        self._preamble_lines: List[str] = []
        self._ensure_file_exists()
        self.load()

    def _ensure_file_exists(self) -> None:
        """Initializes default core_profile.md on disk if not present."""
        if not os.path.exists(self.file_path):
            atomic_write_text(self.file_path, DEFAULT_CORE_PROFILE)

    def load(self) -> None:
        """Parses markdown non-destructively, preserving headers, entries, and comments."""
        self._section_blocks.clear()
        self._preamble_lines.clear()

        if not os.path.isfile(self.file_path):
            return

        current_block: Optional[SectionBlock] = None

        with open(self.file_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\r\n")
                stripped = line.strip()

                if stripped.startswith("## "):
                    sec_title = stripped[3:].strip()
                    current_block = SectionBlock(sec_title)
                    self._section_blocks[sec_title] = current_block
                    continue

                if current_block is not None:
                    current_block.raw_lines.append(line)
                else:
                    self._preamble_lines.append(line)

    def save(self) -> None:
        """Serializes sections and preserved markdown back to disk atomically."""
        lines = list(self._preamble_lines) if self._preamble_lines else ["# User Core Profile", ""]
        while lines and not lines[-1].strip():
            lines.pop()

        for sec_title, block in self._section_blocks.items():
            lines.append("")
            lines.append(f"## {sec_title}")
            for l in block.raw_lines:
                lines.append(l)

        atomic_write_text(self.file_path, "\n".join(lines).rstrip() + "\n")

    def update_profile(self, section: str, key: str, value: str) -> str:
        """Updates, adds, or deletes an item from core_profile.md, syncing latest disk changes first."""
        self.load()

        clean_sec = section.strip()
        clean_key = key.strip()
        clean_val = value.strip()

        target_block = None
        for title, block in self._section_blocks.items():
            if title.lower() == clean_sec.lower():
                target_block = block
                break

        if target_block is None:
            target_block = SectionBlock(clean_sec)
            self._section_blocks[clean_sec] = target_block

        if not clean_val:
            deleted_key = target_block.delete_entry(clean_key)
            if deleted_key:
                self.save()
                return f"Deleted rule '{deleted_key}' from section '{target_block.title}'."
            return f"Key '{clean_key}' not found in section '{target_block.title}'; nothing deleted."

        _, canonical_key = target_block.set_entry(clean_key, clean_val)
        self.save()
        return f"Updated '{target_block.title}' -> '{canonical_key}': '{clean_val}'."

    def get_profile_markdown(self) -> str:
        """Returns the full core profile markdown string directly from disk."""
        if not os.path.isfile(self.file_path):
            return DEFAULT_CORE_PROFILE
        with open(self.file_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    @property
    def sections(self) -> Dict[str, Dict[str, str]]:
        """Returns all parsed profile sections and their key-value pairs."""
        res: Dict[str, Dict[str, str]] = {}
        for title, block in self._section_blocks.items():
            res[title] = dict(block.get_entries())
        return res

    def get_section_entries(self, section: str) -> Dict[str, str]:
        """Returns entries under a given section header."""
        for title, block in self._section_blocks.items():
            if title.lower() == section.strip().lower():
                return dict(block.get_entries())
        return {}
