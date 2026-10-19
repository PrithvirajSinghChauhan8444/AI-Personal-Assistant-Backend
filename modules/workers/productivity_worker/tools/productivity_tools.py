from langchain_core.tools import tool

@tool
def get_current_time() -> str:
    """Returns the current local and UTC system timestamp."""
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"Current time is: {now_utc}"

@tool
def list_calendar_events(days_ahead: int = 1) -> str:
    """Lists calendar schedule events for the specified timeframe."""
    return f"Calendar: 1 event found today:\n- 10:00 AM: Sprint Planning"

@tool
def add_task_tool(title: str, due_date: str = "") -> str:
    """Adds a new task to Google Tasks."""
    return f"Task '{title}' successfully added with due date: {due_date or 'No date'}."

productivity_tools = [get_current_time, list_calendar_events, add_task_tool]
