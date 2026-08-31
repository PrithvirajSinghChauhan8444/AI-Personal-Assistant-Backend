import json
import os
import sys
from typing import List, Dict, Any
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


def delete_calendar_event(event_id: str, account: str = "personal") -> str:
    """Deletes an event from the calendar.

    Args:
        event_id (str): The unique ID of the calendar event to delete.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: delete_calendar_event")
    print(f"   Args: event_id={event_id}, account={account}")
    try:
        success = delete_existing_event(event_id=event_id, account=account)
        if success:
            return f"Event with ID '{event_id}' was successfully deleted from account '{account}'."
        return f"Failed to delete event with ID '{event_id}' on account '{account}'."
    except Exception as e:
        return f"Error deleting calendar event: {e}"

productivity_worker_tool_delete_event = StructuredTool.from_function(
    func=delete_calendar_event,
    name="delete_calendar_event",
    description="" # docstring
)
