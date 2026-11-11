"""Tool definitions for ProductivityAgent."""

from typing import List

from src.agents.contracts import ToolDefinition

PRODUCTIVITY_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="gmail_list",
        category="workspace",
        description="Lists recent emails matching query via Google Workspace OAuth client.",
        risk="LOW",
        prompt_usage_tip="Use to check incoming mail, search for notifications, or locate message IDs for gmail_read.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias: primary, college, personal"},
                "query": {"type": "string", "description": "Gmail query (e.g. 'is:unread', default: 'in:inbox')", "default": "in:inbox"},
                "limit": {"type": "integer", "description": "Maximum emails to retrieve (default: 10)", "default": 10},
            },
        },
    ),
    ToolDefinition(
        name="gmail_read",
        category="workspace",
        description="Reads full email headers and decoded body content for a specific message ID.",
        risk="LOW",
        prompt_usage_tip="Use after obtaining message IDs from gmail_list to review full email conversations.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias: primary, college, personal"},
                "message_id": {"type": "string", "description": "Gmail message ID returned from gmail_list"},
            },
            "required": ["message_id"],
        },
    ),
    ToolDefinition(
        name="gmail_send_draft",
        category="workspace",
        description="Creates a new email draft in Gmail without sending it immediately.",
        risk="MEDIUM",
        prompt_usage_tip="Use to prepare email communications. Drafts allow user review before dispatch.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias: primary, college, personal"},
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email message body"},
            },
            "required": ["to", "subject", "body"],
        },
    ),
    ToolDefinition(
        name="calendar_list",
        category="workspace",
        description="Lists scheduled Google Calendar events within a specified time window.",
        risk="LOW",
        prompt_usage_tip="Use to check schedules, meetings, and upcoming deadlines.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias: primary, college, personal"},
                "time_min": {"type": "string", "description": "RFC3339 timestamp start filter (default: start of today)"},
                "time_max": {"type": "string", "description": "RFC3339 timestamp end filter (default: 7 days ahead)"},
                "limit": {"type": "integer", "description": "Maximum events to return (default: 10)", "default": 10},
            },
        },
    ),
]
