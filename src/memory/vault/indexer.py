"""Knowledge Vault indexer and cross-file search."""

from __future__ import annotations

from pathlib import Path
from typing import List

from src.memory.profiles.atomic_file import atomic_write_text
from src.memory.vault.templates import DEFAULT_INDEX_MD


class VaultIndexer:
    """Manages index.md table of contents and keyword searches across the vault."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.index_file = self.root_dir / "index.md"
        self._ensure_index_file()

    def _ensure_index_file(self) -> None:
        if not self.index_file.is_file():
            atomic_write_text(str(self.index_file), DEFAULT_INDEX_MD.strip() + "\n")

    def read_index(self) -> str:
        """Reads the full index.md contents."""
        self._ensure_index_file()
        return self.index_file.read_text(encoding="utf-8").strip()

    def register_entry(self, relative_path: str, description: str) -> None:
        """Registers a relative path and its description into index.md if not present."""
        content = self.read_index()
        entry_tag = f"[{relative_path}]"
        if entry_tag in content:
            return

        new_line = f"- [{relative_path}]: {description.strip()}\n"
        atomic_write_text(str(self.index_file), content.rstrip() + "\n" + new_line)

    def ensure_indexed(self, relative_path: str) -> None:
        """Auto-registers a file if it lacks an entry in index.md."""
        content = self.read_index()
        if f"[{relative_path}]" not in content:
            name = Path(relative_path).stem.replace("_", " ").title()
            self.register_entry(relative_path, f"Knowledge notes and configuration for {name}.")

    def search_all(self, query: str) -> str:
        """Performs a case-insensitive keyword search across all markdown files."""
        clean_q = query.strip().lower()
        if not clean_q:
            return self.read_index()

        results: List[str] = [f"### Vault search results for '{query}':"]
        for md_file in sorted(self.root_dir.rglob("*.md")):
            rel_path = md_file.relative_to(self.root_dir).as_posix()
            try:
                text = md_file.read_text(encoding="utf-8")
                matched = [
                    line.strip()
                    for line in text.splitlines()
                    if clean_q in line.lower() and not line.strip().startswith("#")
                ]
                if matched:
                    results.append(f"\n**{rel_path}**:")
                    results.extend(f"  {line}" for line in matched[:5])
            except Exception:
                continue

        return "\n".join(results) if len(results) > 1 else f"No matches found in memory vault for '{query}'."
