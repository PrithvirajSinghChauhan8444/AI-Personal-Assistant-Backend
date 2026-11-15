"""Tier 1 Core User Profile Manager for Layer 5 Memory Layer."""

import os
from collections import OrderedDict
from typing import Dict, Optional

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
    """Manages reading, modifying, and serializing ~/.config/ai-assistant/memory/core_profile.md."""

    def __init__(self, file_path: str) -> None:
        self.file_path = os.path.abspath(os.path.expanduser(file_path))
        self._sections: OrderedDict[str, OrderedDict[str, str]] = OrderedDict()
        self._ensure_file_exists()
        self.load()

    def _ensure_file_exists(self) -> None:
        """Initializes default core_profile.md on disk if not present."""
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(DEFAULT_CORE_PROFILE)

    def load(self) -> None:
        """Parses the markdown file into sections and key-value pairs."""
        self._sections.clear()
        if not os.path.isfile(self.file_path):
            return

        current_section = "General"
        self._sections[current_section] = OrderedDict()

        with open(self.file_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("# "):
                    continue

                if line.startswith("## "):
                    current_section = line[3:].strip()
                    if current_section not in self._sections:
                        self._sections[current_section] = OrderedDict()
                    continue

                if line.startswith("- "):
                    item_text = line[2:].strip()
                    if ":" in item_text:
                        k, v = item_text.split(":", 1)
                        self._sections[current_section][k.strip()] = v.strip()
                    else:
                        self._sections[current_section][item_text] = ""

    def save(self) -> None:
        """Serializes current sections into structured Markdown back to disk."""
        lines = ["# User Core Profile", ""]
        for section_name, entries in self._sections.items():
            if not entries and section_name == "General":
                continue
            lines.append(f"## {section_name}")
            for k, v in entries.items():
                if v:
                    lines.append(f"- {k}: {v}")
                else:
                    lines.append(f"- {k}:")
            lines.append("")

        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).strip() + "\n")

    def update_profile(self, section: str, key: str, value: str) -> str:
        """Updates, adds, or deletes an item from core_profile.md."""
        target_section = self._find_or_create_section(section.strip())
        clean_key = key.strip()
        clean_value = value.strip()

        if not clean_value:
            # Delete key if present
            matching_key = self._find_matching_key(target_section, clean_key)
            if matching_key and matching_key in self._sections[target_section]:
                del self._sections[target_section][matching_key]
                self.save()
                return f"Deleted rule '{clean_key}' from section '{target_section}'."
            return f"Key '{clean_key}' not found in section '{target_section}'; nothing deleted."

        # Insert or update
        matching_key = self._find_matching_key(target_section, clean_key) or clean_key
        self._sections[target_section][matching_key] = clean_value
        self.save()
        return f"Updated '{target_section}' -> '{matching_key}': '{clean_value}'."

    def get_profile_markdown(self) -> str:
        """Returns the full core profile markdown string."""
        if not os.path.isfile(self.file_path):
            return DEFAULT_CORE_PROFILE
        with open(self.file_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    @property
    def sections(self) -> Dict[str, Dict[str, str]]:
        """Returns all parsed profile sections and their key-value pairs."""
        return {k: dict(v) for k, v in self._sections.items()}

    def get_section_entries(self, section: str) -> Dict[str, str]:
        """Returns entries under a given section header."""
        for sec_name, entries in self._sections.items():
            if sec_name.lower() == section.strip().lower():
                return dict(entries)
        return {}

    def _find_or_create_section(self, section: str) -> str:
        for existing in self._sections.keys():
            if existing.lower() == section.lower():
                return existing
        self._sections[section] = OrderedDict()
        return section

    def _find_matching_key(self, section: str, key: str) -> Optional[str]:
        if section not in self._sections:
            return None
        for k in self._sections[section].keys():
            if k.lower() == key.lower():
                return k
        return None
