from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from modules.workers.obsidian_worker.integrations.obsidian_vault import (
    create_note as _create_note,
    append_note as _append_note,
    search_vault as _search_vault,
    get_backlinks as _get_backlinks,
    get_properties as _get_props,
    update_properties as _update_props,
    create_or_update_canvas as _create_canvas
)

@tool
def create_obsidian_note(filename: str, content: str, folder: str = "") -> str:
    """Creates a new markdown note in the Obsidian vault."""
    return _create_note(filename=filename, content=content, folder=folder)

@tool
def append_obsidian_note(filename: str, content: str, folder: str = "") -> str:
    """Appends content to an existing note in the Obsidian vault."""
    return _append_note(filename=filename, content=content, folder=folder)

@tool
def search_obsidian_vault(query: str, folder: str = "") -> str:
    """Searches the Obsidian vault for notes matching a query."""
    matches = _search_vault(query=query, folder=folder)
    if not matches:
        return f"No vault notes found matching '{query}'."
    lines = [f"Found {len(matches)} matching vault notes:"]
    for m in matches:
        lines.append(f"- {m['file']} ({m['match']})")
    return "\n".join(lines)

@tool
def get_note_backlinks(filename: str) -> str:
    """Retrieves list of notes that link to the specified note."""
    links = _get_backlinks(filename)
    if not links:
        return f"No backlinks found for '{filename}'."
    return f"Backlinks to '{filename}':\n" + "\n".join(f"- {l}" for l in links)

@tool
def create_canvas_tool(canvas_name: str, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], folder: str = "") -> str:
    """Creates or updates an Obsidian Canvas visual diagram file."""
    return _create_canvas(canvas_name=canvas_name, nodes=nodes, edges=edges, folder=folder)

@tool
def manage_properties_tool(filename: str, action: str = "get", properties: Optional[Dict[str, Any]] = None) -> str:
    """Reads or updates YAML frontmatter properties for a note."""
    if action == "get":
        return str(_get_props(filename))
    return str(_update_props(filename, properties or {}))

obsidian_tools = [
    create_obsidian_note,
    append_obsidian_note,
    search_obsidian_vault,
    get_note_backlinks,
    create_canvas_tool,
    manage_properties_tool
]
