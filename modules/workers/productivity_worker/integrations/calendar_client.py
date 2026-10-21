from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from modules.infrastructure.security.oauth import get_google_credentials

def get_calendar_service(account: str = "personal"):
    """Authenticates and returns the Google Calendar API service."""
    creds = get_google_credentials(account)
    if not creds:
        raise Exception(f"Google Calendar authentication failed for account '{account}'.")
    return build('calendar', 'v3', credentials=creds)

def list_calendar_events(max_results: int = 5, account: str = "both") -> List[Dict[str, Any]]:
    """Fetches upcoming calendar events across requested account(s)."""
    from src.CoreFunctions.Integrations.Calendar.read_event import list_upcoming_events
    accounts_to_check = ["personal", "college"] if account == "both" else [account]
    all_events = []
    for acc in accounts_to_check:
        try:
            evs = list_upcoming_events(max_results=max_results, account=acc)
            if evs and isinstance(evs, list):
                for e in evs:
                    e_copy = dict(e)
                    e_copy["account"] = acc
                    all_events.append(e_copy)
        except Exception:
            pass
    return all_events

def create_calendar_event(
    summary: str,
    start_time: str,
    duration: int = 1,
    description: Optional[str] = None,
    color: str = "orange",
    account: str = "personal"
) -> Optional[Dict[str, Any]]:
    """Creates a new event on Google Calendar."""
    from src.CoreFunctions.Integrations.Calendar.create_event import create_new_event
    return create_new_event(
        summary=summary,
        start_time=start_time,
        duration=duration,
        description=description,
        color=color,
        account=account
    )

def delete_calendar_event(event_id: str, account: str = "personal") -> bool:
    """Deletes an event from Google Calendar."""
    from src.CoreFunctions.Integrations.Calendar.delete_event import delete_existing_event
    return delete_existing_event(event_id=event_id, account=account)
