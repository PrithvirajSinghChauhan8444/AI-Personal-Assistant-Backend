"""Tool definitions for ProductivityAgent."""

from typing import List

from src.agents.contracts import ToolDefinition

PRODUCTIVITY_TOOLS: List[ToolDefinition] = [
    # Authentication & Account Tools
    ToolDefinition(
        name="google_auth_login",
        category="workspace",
        description="Initiates Google Workspace OAuth flow, starts local callback receiver, and prints the direct authorization link to terminal.",
        risk="LOW",
        prompt_usage_tip="Call this when Google credentials/tokens are missing or expired, or when the user asks to log in / connect their Google account.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email", "default": "email1"},
                "port": {"type": "integer", "description": "Local callback port (default: 9915)", "default": 9915},
            },
        },
    ),

    # Gmail Tools
    ToolDefinition(
        name="gmail_list",
        category="workspace",
        description="Lists recent emails matching query via Google Workspace OAuth client.",
        risk="LOW",
        prompt_usage_tip="Use to check incoming mail, search for notifications, or locate message IDs for gmail_read.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email"},
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
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email"},
                "message_id": {"type": "string", "description": "Gmail message ID returned from gmail_list"},
            },
            "required": ["message_id"],
        },
    ),
    ToolDefinition(
        name="gmail_check_unread",
        category="workspace",
        description="Fetches count and headers of unread emails across inbox.",
        risk="LOW",
        prompt_usage_tip="Use during briefings or status checks to triage incoming emails quickly.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email"},
                "limit": {"type": "integer", "description": "Maximum unread emails to retrieve (default: 5)", "default": 5},
            },
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
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email"},
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email message body"},
            },
            "required": ["to", "subject", "body"],
        },
    ),
    ToolDefinition(
        name="gmail_reply",
        category="workspace",
        description="Replies directly to an existing email thread, preserving conversation headers and thread ID.",
        risk="MEDIUM",
        prompt_usage_tip="Use to reply to a specific email thread. Prefer drafting first unless direct reply is explicitly instructed.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email"},
                "message_id": {"type": "string", "description": "Original Gmail message ID to reply to"},
                "body": {"type": "string", "description": "Reply email body content"},
            },
            "required": ["message_id", "body"],
        },
    ),
    ToolDefinition(
        name="gmail_send",
        category="workspace",
        description="Dispatches an email directly to a recipient. High risk operation.",
        risk="HIGH",
        prompt_usage_tip="Use only when the user explicitly instructs immediate email sending without a draft.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email"},
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body content"},
            },
            "required": ["to", "subject", "body"],
        },
    ),

    # Calendar Tools
    ToolDefinition(
        name="calendar_list",
        category="workspace",
        description="Lists scheduled Google Calendar events within a specified time window.",
        risk="LOW",
        prompt_usage_tip="Use to check schedules, meetings, and upcoming deadlines.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email"},
                "time_min": {"type": "string", "description": "RFC3339 timestamp start filter (default: start of today)"},
                "time_max": {"type": "string", "description": "RFC3339 timestamp end filter (default: 7 days ahead)"},
                "limit": {"type": "integer", "description": "Maximum events to return (default: 10)", "default": 10},
            },
        },
    ),
    ToolDefinition(
        name="calendar_create_event",
        category="workspace",
        description="Creates a new event on Google Calendar with start time, duration, and notes.",
        risk="MEDIUM",
        prompt_usage_tip="Use to schedule meetings, appointments, or deadlines. Verify conflicts with calendar_list first.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email"},
                "summary": {"type": "string", "description": "Title or summary of the event"},
                "start_time": {"type": "string", "description": "ISO/RFC3339 start timestamp (e.g. '2026-11-14T10:00:00Z')"},
                "duration_hours": {"type": "number", "description": "Duration in hours (default: 1.0)", "default": 1.0},
                "description": {"type": "string", "description": "Optional notes or meeting agenda"},
                "color": {"type": "string", "description": "Optional color name (blue, green, orange, red, purple)"},
            },
            "required": ["summary", "start_time"],
        },
    ),
    ToolDefinition(
        name="calendar_edit_event",
        category="workspace",
        description="Edits an existing event on Google Calendar by event ID.",
        risk="MEDIUM",
        prompt_usage_tip="Use to reschedule or modify meeting title, time, or description.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email"},
                "event_id": {"type": "string", "description": "Google Calendar event ID to modify"},
                "summary": {"type": "string", "description": "Updated event summary/title"},
                "start_time": {"type": "string", "description": "Updated start timestamp"},
                "duration_hours": {"type": "number", "description": "Updated duration in hours"},
                "description": {"type": "string", "description": "Updated notes or agenda"},
                "color": {"type": "string", "description": "Updated color name"},
            },
            "required": ["event_id"],
        },
    ),
    ToolDefinition(
        name="calendar_delete_event",
        category="workspace",
        description="Permanently deletes an event from Google Calendar by event ID.",
        risk="HIGH",
        prompt_usage_tip="Use when meetings or calendar reminders are cancelled.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email"},
                "event_id": {"type": "string", "description": "Google Calendar event ID to delete"},
            },
            "required": ["event_id"],
        },
    ),

    # Google Tasks Tools
    ToolDefinition(
        name="tasks_list",
        category="workspace",
        description="Lists pending items from the user's Google Tasks.",
        risk="LOW",
        prompt_usage_tip="Use to inspect pending to-do items and reminders.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email"},
                "task_list_id": {"type": "string", "description": "Optional task list ID (defaults to '@default')"},
                "limit": {"type": "integer", "description": "Maximum tasks to return (default: 10)", "default": 10},
            },
        },
    ),
    ToolDefinition(
        name="tasks_create",
        category="workspace",
        description="Creates a new to-do task item in Google Tasks.",
        risk="MEDIUM",
        prompt_usage_tip="Use to record action items, reminders, and homework assignments.",
        parameters={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account alias (e.g. email1, email2) or email"},
                "task_list_id": {"type": "string", "description": "Optional task list ID (defaults to '@default')"},
                "title": {"type": "string", "description": "Title of the task to add"},
                "notes": {"type": "string", "description": "Optional notes or details"},
                "due": {"type": "string", "description": "Optional RFC3339 due timestamp"},
            },
            "required": ["title"],
        },
    ),

    # System Time
    ToolDefinition(
        name="sys_get_time",
        category="system",
        description="Returns the current system timestamp in both local time and UTC.",
        risk="LOW",
        prompt_usage_tip="Use to verify today's date, day of week, or current time before scheduling events.",
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
]
