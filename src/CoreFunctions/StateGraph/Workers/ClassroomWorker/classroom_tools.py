from langchain_core.tools import StructuredTool
from src.CoreFunctions.tools import (
    request_human_intervention_sync, request_human_intervention,
    fetch_classroom_courses, fetch_classroom_assignments, fetch_classroom_announcements,
    fetch_classroom_assignment_details, download_classroom_materials_tool,
    submit_classroom_assignment_tool
)

human_intervention_tool = StructuredTool.from_function(
    func=request_human_intervention_sync,
    name="request_human_intervention",
    description="Pauses the automated process and requests manual intervention from the human user. Use this when you hit CAPTCHAs, bot checks, 2FA prompts, or roadblocks/issues you cannot solve yourself.",
    coroutine=request_human_intervention
)

classroom_tools = [
    StructuredTool.from_function(fetch_classroom_courses),
    StructuredTool.from_function(fetch_classroom_assignments),
    StructuredTool.from_function(fetch_classroom_announcements),
    StructuredTool.from_function(fetch_classroom_assignment_details),
    StructuredTool.from_function(download_classroom_materials_tool),
    StructuredTool.from_function(submit_classroom_assignment_tool),
    human_intervention_tool
]
