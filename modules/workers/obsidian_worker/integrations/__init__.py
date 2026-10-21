"""Obsidian Vault and Canvas integrations for obsidian_worker."""
from .obsidian_vault import (
    create_note,
    append_note,
    search_vault,
    get_backlinks,
    get_properties,
    update_properties,
    create_or_update_canvas
)

__all__ = [
    "create_note",
    "append_note",
    "search_vault",
    "get_backlinks",
    "get_properties",
    "update_properties",
    "create_or_update_canvas"
]
