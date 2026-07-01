from src.CoreFunctions.SharedTools import human_intervention_tool
from .obsidian_worker_tool_create_note import create_obsidian_note
from .obsidian_worker_tool_append_note import append_to_obsidian_note
from .obsidian_worker_tool_search_vault import search_obsidian_vault
from .obsidian_worker_tool_get_backlinks import get_note_backlinks
from .obsidian_worker_tool_get_properties import get_note_properties
from .obsidian_worker_tool_update_properties import update_note_properties
from .obsidian_worker_tool_create_or_update_canvas import create_or_update_obsidian_canvas

obsidian_tools = [
    create_obsidian_note,
    append_to_obsidian_note,
    search_obsidian_vault,
    get_note_backlinks,
    get_note_properties,
    update_note_properties,
    create_or_update_obsidian_canvas,
    human_intervention_tool
]
