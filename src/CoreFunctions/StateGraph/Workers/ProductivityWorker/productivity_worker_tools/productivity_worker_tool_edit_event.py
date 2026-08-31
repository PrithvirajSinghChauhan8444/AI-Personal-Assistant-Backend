import json
import os
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime
from langchain_core.tools import StructuredTool

# Import all integrations and infra helpers that tools might need
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector, delete_vector_fact, rebuild_skills_vector_store, search_skills_vector
from src.CoreFunctions.Infrastructure.file_vector_store import index_file, index_directory_recursive, search_files_semantically, rag_qa_file
from src.CoreFunctions.Infrastructure.auth_utils import verify_password
from src.CoreFunctions.Infrastructure.security_utils import is_path_safe, is_extension_safe

# Integration imports
try:
    from src.CoreFunctions.Integrations.Google.tasks import add_new_task
    from src.CoreFunctions.Integrations.Calendar.read_event import list_upcoming_events
    from src.CoreFunctions.Integrations.Calendar.create_event import create_new_event
    from src.CoreFunctions.Integrations.Calendar.edit_event import edit_existing_event
    from src.CoreFunctions.Integrations.Calendar.delete_event import delete_existing_event
except ImportError as e:
    pass


def edit_calendar_event(
    event_id: str,
    summary: str = None,
    start_time: str = None,
    duration: int = None,
    description: str = None,
    color: str = None,
    account: str = "personal"
) -> str:
    """Edits an existing event in the calendar.

    Args:
        event_id (str): The unique ID of the calendar event to modify.
        summary (str, optional): The updated title/summary of the event. Defaults to None.
        start_time (str, optional): The updated start time in ISO format (e.g., 'YYYY-MM-DDTHH:MM:SS'). Defaults to None.
        duration (int, optional): The updated duration in hours. Defaults to None.
        description (str, optional): The updated description or notes for the event. Defaults to None.
        color (str, optional): The new color name (e.g. 'orange', 'blue', 'green', 'red', 'purple', 'yellow') or colorId '1'-'11'. Defaults to None.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: edit_calendar_event")
    print(f"   Args: event_id={event_id}, summary={summary}, start_time={start_time}, duration={duration}, description={description}, color={color}, account={account}")
    try:
        result = edit_existing_event(
            event_id=event_id,
            summary=summary,
            start_time_iso=start_time,
            duration_hours=duration,
            description=description,
            color=color,
            account=account
        )
        if result:
            title = result.get('summary', summary or event_id)
            return f"Event '{title}' (ID: {event_id}) updated on account '{account}'. Link: {result.get('htmlLink')}"
        return f"Failed to update event '{event_id}' on account '{account}'."
    except Exception as e:
        return f"Error editing calendar event: {e}"

productivity_worker_tool_edit_event = StructuredTool.from_function(
    func=edit_calendar_event,
    name="edit_calendar_event",
    description="" # docstring
)
