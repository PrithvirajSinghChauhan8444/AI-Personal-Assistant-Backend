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


def create_obsidian_note(filename: str, content: str, folder: str = "") -> str:
    """Creates a new note inside the Obsidian vault with raw content.
    Supports dynamic parent folder creation automatically. You can pass nested paths in the 'filename' parameter (e.g. 'logs/daily.md') or in the 'folder' parameter (e.g. 'logs').

    Args:
        filename (str): The filename of the note (e.g. 'Project Log.md' or 'category/Profile.md').
        content (str): The markdown body content to write in the note.
        folder (str): Optional subfolder within the vault (e.g. 'logs'). Defaults to empty string.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: create_obsidian_note")
    print(f"   Args: filename={filename}, folder={folder}")
    try:
        # Ensure file has .md extension
        if not filename.endswith(".md") and not filename.endswith(".canvas"):
            filename += ".md"
            
        file_path = os.path.abspath(os.path.join(OBSIDIAN_VAULT_PATH, folder, filename))
        
        if not is_path_safe(file_path):
            return f"❌ Security Violation: Access to path '{file_path}' is denied. Out of sandbox."
            
        # Create all parent directories dynamically (handling folders inside filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully created note '{filename}' at path: {file_path}"
    except Exception as e:
        return f"Error creating obsidian note: {e}"

create_obsidian_note = StructuredTool.from_function(
    func=create_obsidian_note,
    name="create_obsidian_note",
    description="" # taken from docstring
)
