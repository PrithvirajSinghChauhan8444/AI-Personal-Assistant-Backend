"""Hierarchical Markdown Knowledge Vault Manager Facade.

Coordinates path validation, atomic file persistence, section edits,
and master indexing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.memory.profiles.atomic_file import atomic_write_text
from src.memory.vault.indexer import VaultIndexer
from src.memory.vault.paths import resolve_vault_dir, safe_vault_path
from src.memory.vault.section_editor import (
    delete_section_entry,
    extract_section,
    filter_lines_by_query,
    upsert_section_entry,
)
from src.memory.vault.templates import (
    DEFAULT_PROFILE_MD,
    DEFAULT_RULES_MD,
    DEFAULT_SYSTEM_INFO_MD,
)


class VaultManager:
    """Manages reading, writing, section-grouping, and indexing for the markdown vault."""

    def __init__(self, vault_dir: Optional[str] = None) -> None:
        self.root_dir = resolve_vault_dir(vault_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.indexer = VaultIndexer(self.root_dir)
        self._ensure_baseline_files()

    def _ensure_baseline_files(self) -> None:
        """Initializes standard vault files, migrating legacy files if present."""
        self._init_profile()
        self._init_file("rules.md", DEFAULT_RULES_MD)
        self._init_file("system_info.md", DEFAULT_SYSTEM_INFO_MD)

    def _init_file(self, filename: str, default_content: str) -> Path:
        target = self.root_dir / filename
        if not target.is_file():
            atomic_write_text(str(target), default_content.strip() + "\n")
        return target

    def _init_profile(self) -> None:
        """Initializes profile.md, migrating legacy core_profile.md and accounts.md if found."""
        profile_path = self.root_dir / "profile.md"
        if profile_path.is_file():
            return

        core_profile = self.root_dir / "core_profile.md"
        accounts = self.root_dir / "accounts.md"

        if core_profile.is_file():
            content = core_profile.read_text(encoding="utf-8").strip()
            if accounts.is_file():
                content += "\n\n" + accounts.read_text(encoding="utf-8").strip()
            atomic_write_text(str(profile_path), content + "\n")
            return

        atomic_write_text(str(profile_path), DEFAULT_PROFILE_MD.strip() + "\n")

    def read(
        self,
        file_path: Optional[str] = None,
        query: Optional[str] = None,
        section: Optional[str] = None,
    ) -> str:
        """Reads or searches content in the vault."""
        if not file_path:
            return self.indexer.search_all(query or "")

        target = safe_vault_path(self.root_dir, file_path)
        if not target.is_file():
            return f"Error: File '{file_path}' not found in memory vault."

        content = target.read_text(encoding="utf-8")
        if section:
            return extract_section(content, section)
        if query:
            return filter_lines_by_query(content, query, file_path)
        return content.strip()

    def add(
        self,
        file_path: str,
        section: str,
        content: str,
        key: Optional[str] = None,
    ) -> str:
        """Adds or updates an entry within a specified section of a markdown file."""
        target = safe_vault_path(self.root_dir, file_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        existing_text = target.read_text(encoding="utf-8") if target.is_file() else ""
        updated_text, status = upsert_section_entry(existing_text, section, content, key)

        atomic_write_text(str(target), updated_text)
        self.indexer.ensure_indexed(file_path)
        return f"Successfully {status} in '{file_path}' under section '## {section}'."

    def remove(self, file_path: str, section: str, key: str) -> str:
        """Removes an entry from a section in a markdown file."""
        target = safe_vault_path(self.root_dir, file_path)
        if not target.is_file():
            return f"Error: File '{file_path}' not found."

        existing_text = target.read_text(encoding="utf-8")
        updated_text, removed = delete_section_entry(existing_text, section, key)

        if not removed:
            return f"Key or pattern '{key}' was not found in '{file_path}' section '## {section}'."

        atomic_write_text(str(target), updated_text)
        return f"Successfully removed '{key}' from '{file_path}' section '## {section}'."

    def create(self, file_path: str, description: str, initial_content: str = "") -> str:
        """Creates a new topic markdown file or subdirectory and updates index.md."""
        target = safe_vault_path(self.root_dir, file_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if not initial_content.strip():
            title = target.stem.replace("_", " ").title()
            initial_content = f"# {title}\n\n## Overview\n"

        atomic_write_text(str(target), initial_content.strip() + "\n")
        self.indexer.register_entry(file_path, description)
        return f"Created file '{file_path}' and registered in index.md."

    def get_profile_markdown(self) -> str:
        """Returns the current profile.md contents for startup grounding."""
        return self.read("profile.md")

    def get_rules_markdown(self) -> str:
        """Returns the current rules.md contents for startup grounding."""
        return self.read("rules.md")
