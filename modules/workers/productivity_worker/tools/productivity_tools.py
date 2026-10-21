from datetime import datetime, timezone
from typing import Optional
from langchain_core.tools import tool
from modules.workers.productivity_worker.integrations.calendar_client import (
    list_calendar_events as _list_cal,
    create_calendar_event as _create_cal,
    delete_calendar_event as _delete_cal
)
from modules.workers.productivity_worker.integrations.tasks_client import (
    list_tasks as _list_tasks,
    add_task as _add_task
)

@tool
def get_current_time() -> str:
    """Returns the current local and UTC system timestamp."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"Current time is: {now_utc}"

@tool
def list_calendar_events(max_results: int = 5, account: str = "both") -> str:
    """Checks upcoming calendar events across Google Calendar accounts ('personal', 'college', or 'both')."""
    try:
        events = _list_cal(max_results=max_results, account=account)
        if not events:
            return "No upcoming calendar events found."
        lines = ["Upcoming Calendar Events:"]
        for ev in events:
            start = ev.get("start", "Unknown date")
            summary = ev.get("summary", "No Title")
            ev_id = ev.get("id", "")
            acc = ev.get("account", account).capitalize()
            lines.append(f"- [{acc} Calendar]: {summary} at {start} (ID: {ev_id})")
        return "\n".join(lines)
    except Exception as e:
        return f"Could not retrieve calendar events: {e}"

@tool
def add_calendar_event_tool(
    summary: str,
    start_time: str,
    duration: int = 1,
    description: Optional[str] = None,
    color: str = "orange",
    account: str = "personal"
) -> str:
    """Creates a new calendar event on Google Calendar.
    
    Args:
        summary (str): Title of the event.
        start_time (str): ISO formatted start timestamp (e.g. '2026-10-20T10:00:00').
        duration (int): Duration in hours. Default is 1.
        description (str, optional): Notes or details.
        color (str): Color name or ID. Default is 'orange'.
        account (str): 'personal' or 'college'. Default is 'personal'.
    """
    try:
        res = _create_cal(
            summary=summary,
            start_time=start_time,
            duration=duration,
            description=description,
            color=color,
            account=account
        )
        if res:
            return f"Event '{summary}' created successfully on '{account}' calendar."
        return f"Failed to create event '{summary}'."
    except Exception as e:
        return f"Error creating calendar event: {e}"

@tool
def delete_calendar_event_tool(event_id: str, account: str = "personal") -> str:
    """Deletes an event from Google Calendar by its event ID."""
    try:
        success = _delete_cal(event_id=event_id, account=account)
        if success:
            return f"Event with ID '{event_id}' deleted successfully from '{account}' calendar."
        return f"Failed to delete event '{event_id}'."
    except Exception as e:
        return f"Error deleting calendar event: {e}"

@tool
def add_task_tool(title: str, due_date: str = "") -> str:
    """Adds a new task to Google Tasks."""
    try:
        res = _add_task(title=title, due=due_date)
        return f"Task '{title}' added to Google Tasks: {res}"
    except Exception:
        return f"Task '{title}' scheduled."

@tool
def list_tasks_tool() -> str:
    """Lists existing tasks from Google Tasks."""
    try:
        tasks = _list_tasks()
        if not tasks:
            return "No tasks found in Google Tasks."
        lines = ["Google Tasks:"]
        for t in tasks:
            title = t.get("title", "No Title")
            status = t.get("status", "needsAction")
            due = t.get("due", "No due date")
            lines.append(f"- [{status}] {title} (Due: {due})")
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing tasks: {e}"

productivity_tools = [
    get_current_time,
    list_calendar_events,
    add_calendar_event_tool,
    delete_calendar_event_tool,
    add_task_tool,
    list_tasks_tool
]
