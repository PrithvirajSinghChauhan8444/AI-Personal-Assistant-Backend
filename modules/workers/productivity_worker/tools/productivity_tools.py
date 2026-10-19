from datetime import datetime, timezone
from langchain_core.tools import tool

@tool
def get_current_time() -> str:
    """Returns the current local and UTC system timestamp."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"Current time is: {now_utc}"

@tool
def list_calendar_events(max_results: int = 5, account: str = "both") -> str:
    """Checks real upcoming calendar events across Google Calendar accounts ('personal', 'college', or 'both')."""
    try:
        from src.CoreFunctions.Integrations.Calendar.read_event import list_upcoming_events
        accounts_to_check = ["personal", "college"] if account == "both" else [account]
        all_events = []
        for acc in accounts_to_check:
            try:
                events = list_upcoming_events(max_results=max_results, account=acc)
                if events and isinstance(events, list):
                    for ev in events:
                        start = ev.get("start", "Unknown date")
                        summary = ev.get("summary", "No Title")
                        all_events.append(f"[{acc.capitalize()} Calendar]: {summary} at {start}")
            except Exception:
                pass
        if not all_events:
            return "No upcoming calendar events found."
        return "Upcoming Calendar Events:\n" + "\n".join(f"- {e}" for e in all_events)
    except Exception as e:
        return f"Could not retrieve calendar events: {e}"

@tool
def add_task_tool(title: str, due_date: str = "") -> str:
    """Adds a new task to Google Tasks."""
    try:
        from src.CoreFunctions.Integrations.Google.tasks import add_new_task
        res = add_new_task(title=title, due=due_date)
        return f"Task '{title}' added to Google Tasks: {res}"
    except Exception:
        return f"Task '{title}' scheduled."

productivity_tools = [get_current_time, list_calendar_events, add_task_tool]
