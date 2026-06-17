from langchain_core.tools import StructuredTool
from src.CoreFunctions.tools import (
    request_human_intervention_sync, request_human_intervention,
    run_terminal_tool, run_python_tool, web_search, read_file_tool,
    create_file_tool, update_skill_tool, search_skills_tool
)

human_intervention_tool = StructuredTool.from_function(
    func=request_human_intervention_sync,
    name="request_human_intervention",
    description="Pauses the automated process and requests manual intervention from the human user. Use this when you hit CAPTCHAs, bot checks, 2FA prompts, or roadblocks/issues you cannot solve yourself.",
    coroutine=request_human_intervention
)

search_skills_tool_wrapped = StructuredTool.from_function(
    func=search_skills_tool,
    name="search_skills",
    description="Semantically searches for available system skills matching the query. This tool is read-only and does not require password verification."
)

misc_tools = [
    StructuredTool.from_function(run_terminal_tool),
    StructuredTool.from_function(run_python_tool),
    StructuredTool.from_function(web_search),
    StructuredTool.from_function(read_file_tool),
    StructuredTool.from_function(create_file_tool),
    StructuredTool.from_function(update_skill_tool, name="update_skill"),
    search_skills_tool_wrapped,
    human_intervention_tool
]
