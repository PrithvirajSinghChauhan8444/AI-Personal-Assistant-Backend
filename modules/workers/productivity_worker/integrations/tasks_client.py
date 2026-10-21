from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from modules.infrastructure.security.oauth import get_google_credentials

def get_tasks_service(account: str = "personal"):
    """Authenticates and returns the Google Tasks API service."""
    creds = get_google_credentials(account)
    if not creds:
        raise Exception(f"Google Tasks authentication failed for account '{account}'.")
    return build('tasks', 'v1', credentials=creds)

def list_tasks() -> List[Dict[str, Any]]:
    """Lists tasks from Google Tasks."""
    from src.CoreFunctions.Integrations.Google.tasks import list_all_tasks
    return list_all_tasks()

def add_task(title: str, due: str = "") -> Any:
    """Adds a new task to Google Tasks."""
    from src.CoreFunctions.Integrations.Google.tasks import add_new_task
    return add_new_task(title=title, due=due)
