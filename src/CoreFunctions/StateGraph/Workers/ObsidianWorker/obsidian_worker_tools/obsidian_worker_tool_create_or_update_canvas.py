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


def create_or_update_obsidian_canvas(canvas_name: str, nodes: List[dict], edges: List[dict] = None, folder: str = "") -> str:
    """Creates or updates an Obsidian Canvas (.canvas) infinite whiteboard.

    Args:
        canvas_name (str): The filename of the canvas (e.g. 'Project Mindmap.canvas').
        nodes (list): A list of dictionaries representing nodes. Each node can contain:
                      - 'id' (str, unique)
                      - 'type' (str: 'text' or 'file' or 'group')
                      - 'x' (int), 'y' (int)
                      - 'width' (int), 'height' (int)
                      - 'text' (str, if type is 'text')
                      - 'file' (str, if type is 'file', relative path in vault)
                      - 'color' (str, '1' to '6' representing Obsidian colors)
        edges (list, optional): A list of dictionaries representing edges connecting nodes. Each edge can contain:
                      - 'id' (str, unique)
                      - 'fromNode' (str), 'toNode' (str)
                      - 'fromSide' (str: 'top', 'bottom', 'left', 'right')
                      - 'toSide' (str: 'top', 'bottom', 'left', 'right')
                      - 'label' (str, optional)
        folder (str): Optional subfolder within the vault. Defaults to empty string.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: create_or_update_obsidian_canvas")
    print(f"   Args: canvas_name={canvas_name}, folder={folder}")
    try:
        if not canvas_name.endswith(".canvas"):
            canvas_name += ".canvas"
        
        file_path = os.path.abspath(os.path.join(OBSIDIAN_VAULT_PATH, folder, canvas_name))
        
        if not is_path_safe(file_path):
            return f"❌ Security Violation: Access to path '{file_path}' is denied. Out of sandbox."
            
        # Create all parent directories dynamically (handling folders inside canvas name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        canvas_data = {"nodes": [], "edges": []}
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    canvas_data = json.load(f)
            except Exception:
                pass
        
        # Merge or replace nodes
        existing_nodes = {n["id"]: n for n in canvas_data.get("nodes", [])}
        for node in nodes:
            existing_nodes[node["id"]] = node
        canvas_data["nodes"] = list(existing_nodes.values())
        
        # Merge or replace edges
        if edges is not None:
            existing_edges = {e["id"]: e for e in canvas_data.get("edges", [])}
            for edge in edges:
                existing_edges[edge["id"]] = edge
            canvas_data["edges"] = list(existing_edges.values())
            
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(canvas_data, f, indent=4)
            
        return f"Successfully updated Canvas '{canvas_name}' at path: {file_path}"
    except Exception as e:
        return f"Error managing obsidian canvas: {e}"

create_or_update_obsidian_canvas = StructuredTool.from_function(
    func=create_or_update_obsidian_canvas,
    name="create_or_update_obsidian_canvas",
    description="" # taken from docstring
)
