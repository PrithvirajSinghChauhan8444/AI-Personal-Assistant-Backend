from langchain_core.tools import StructuredTool
from src.CoreFunctions.tools import (
    request_human_intervention_sync, request_human_intervention,
    fetch_unread_mails, send_gmail, search_gmail, read_gmail_msg, trash_gmail_msg,
    mark_gmail_read, reply_to_gmail, download_email_attachment_tool,
    send_gmail_with_attachment_tool
)

human_intervention_tool = StructuredTool.from_function(
    func=request_human_intervention_sync,
    name="request_human_intervention",
    description="Pauses the automated process and requests manual intervention from the human user. Use this when you hit CAPTCHAs, bot checks, 2FA prompts, or roadblocks/issues you cannot solve yourself.",
    coroutine=request_human_intervention
)

gmail_tools = [
    StructuredTool.from_function(fetch_unread_mails),
    StructuredTool.from_function(send_gmail),
    StructuredTool.from_function(search_gmail),
    StructuredTool.from_function(read_gmail_msg),
    StructuredTool.from_function(trash_gmail_msg),
    StructuredTool.from_function(mark_gmail_read),
    StructuredTool.from_function(reply_to_gmail),
    StructuredTool.from_function(download_email_attachment_tool),
    StructuredTool.from_function(send_gmail_with_attachment_tool),
    human_intervention_tool
]
