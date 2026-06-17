from langchain_core.tools import StructuredTool
from src.CoreFunctions.tools import (
    request_human_intervention_sync, request_human_intervention,
    create_obsidian_note, append_to_obsidian_note, search_obsidian_vault,
    get_note_backlinks, get_note_properties, update_note_properties,
    create_or_update_obsidian_canvas
)

human_intervention_tool = StructuredTool.from_function(
    func=request_human_intervention_sync,
    name="request_human_intervention",
    description="Pauses the automated process and requests manual intervention from the human user. Use this when you hit CAPTCHAs, bot checks, 2FA prompts, or roadblocks/issues you cannot solve yourself.",
    coroutine=request_human_intervention
)

obsidian_tools = [
    StructuredTool.from_function(create_obsidian_note),
    StructuredTool.from_function(append_to_obsidian_note),
    StructuredTool.from_function(search_obsidian_vault),
    StructuredTool.from_function(get_note_backlinks),
    StructuredTool.from_function(get_note_properties),
    StructuredTool.from_function(update_note_properties),
    StructuredTool.from_function(create_or_update_obsidian_canvas),
    human_intervention_tool
]
