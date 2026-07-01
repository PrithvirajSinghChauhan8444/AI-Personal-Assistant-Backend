import json
import os
import sys
from typing import List, Dict, Any
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
    from src.CoreFunctions.Integrations.System.system_monitor import get_system_stats
    from src.CoreFunctions.Integrations.FileOperations.file_manager import write_file as _write_file, read_file, list_files, create_directory as _create_dir, save_python_code as _save_code
    from src.CoreFunctions.Integrations.SystemControl.execution import run_terminal_command as _run_term, run_python_script as _run_py, launch_app as _launch
    from src.CoreFunctions.Integrations.System.clipboard_ops import copy_to_clipboard as _copy_clip, paste_from_clipboard as _paste_clip
    from src.CoreFunctions.Integrations.System.download_ops import download_file as _download_url
    from src.CoreFunctions.Integrations.Automation.scheduler_ops import schedule_delayed_task as _sched_delay, schedule_task_at_time as _sched_at, list_scheduled_tasks as _sched_list, cancel_scheduled_task as _sched_cancel
    from src.CoreFunctions.Integrations.GoogleDrive.drive_ops import list_drive_files, download_drive_file, upload_drive_file, create_drive_folder, delete_drive_file, get_drive_about
    from src.CoreFunctions.Integrations.Obsidian.obsidian_ops import create_obsidian_note as _create_note, append_to_obsidian_note as _append_note, search_obsidian_vault as _search_vault, get_note_backlinks as _get_backlinks, get_note_properties as _get_props, update_note_properties as _update_props, create_or_update_obsidian_canvas as _canvas_ops
    from src.CoreFunctions.Integrations.Github.github_ops import get_github_profile, list_github_repos, get_github_recent_activity, list_github_commits, list_github_branches, get_github_file_content, search_github_code
except ImportError as e:
    pass


def schedule_delayed_task_tool(description: str, delay_seconds: int, task_type: str = "agent_task", recurrence: str = None) -> str:
    """Schedules a task or reminder to run after a delay in seconds.
    
    Args:
        description (str): The assistant task prompt or reminder message (e.g., 'go for a walk' or 'check unread emails').
        delay_seconds (int): Delay in seconds before execution.
        task_type (str): Either 'reminder' (for simple alarms/alerts to the user) or 'agent_task' (for tasks where the assistant must run tools/workflows). Defaults to 'agent_task'.
        recurrence (str): Recurrence interval: 'minutely', 'hourly', 'daily', 'weekly' or None. Defaults to None.
    """
    return _sched_delay(description, delay_seconds, task_type, recurrence)

schedule_delayed_task_tool = StructuredTool.from_function(
    func=schedule_delayed_task_tool,
    name="schedule_delayed_task_tool",
    description="" # docstring
)
