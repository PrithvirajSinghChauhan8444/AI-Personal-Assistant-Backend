from langchain_core.tools import StructuredTool
from src.CoreFunctions.tools import (
    request_human_intervention_sync, request_human_intervention,
    list_drive_files_tool, download_drive_file_tool, upload_drive_file_tool,
    create_drive_folder_tool, delete_drive_file_tool, get_drive_about_tool
)

human_intervention_tool = StructuredTool.from_function(
    func=request_human_intervention_sync,
    name="request_human_intervention",
    description="Pauses the automated process and requests manual intervention from the human user. Use this when you hit CAPTCHAs, bot checks, 2FA prompts, or roadblocks/issues you cannot solve yourself.",
    coroutine=request_human_intervention
)

drive_tools = [
    StructuredTool.from_function(list_drive_files_tool),
    StructuredTool.from_function(download_drive_file_tool),
    StructuredTool.from_function(upload_drive_file_tool),
    StructuredTool.from_function(create_drive_folder_tool),
    StructuredTool.from_function(delete_drive_file_tool),
    StructuredTool.from_function(get_drive_about_tool),
    human_intervention_tool
]
