import sys
import os

# Ensure we can find the modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from langchain_core.tools import StructuredTool

# Import existing tool functions
from src.CoreFunctions.tools import (
    # Memory
    remember, recall,
    
    # Communication
    fetch_unread_mails, send_gmail, search_gmail, read_gmail_msg, trash_gmail_msg, mark_gmail_read, reply_to_gmail,
    
    # Productivity
    add_google_task, check_calendar_events, add_calendar_event,
    fetch_classroom_courses, fetch_classroom_assignments, fetch_classroom_announcements, fetch_classroom_assignment_details,
    
    # System info
    get_system_health, get_weather, get_time, web_search,
    get_audio_volume, set_audio_volume, mute_audio_toggle,
    get_screen_brightness, set_screen_brightness, control_media_player,
    list_running_processes_tool, terminate_process_tool, lock_desktop_screen, suspend_desktop_system,
    
    # File Ops
    create_file_tool, read_file_tool, list_files_tool, 
    create_dir_tool, save_code_tool,
    index_directory_tool, search_files_semantically_tool, rag_file_qa_tool,
    
    # Execution
    run_terminal_tool, run_python_tool, launch_app_tool,
    
    # Obsidian
    create_obsidian_note, append_to_obsidian_note, search_obsidian_vault,
    get_note_backlinks, get_note_properties, update_note_properties, create_or_update_obsidian_canvas,
    
    # Browser Control
    browser_navigate, browser_click, browser_click_selector, browser_input, browser_input_selector, browser_go_back, browser_read_current_page, browser_read_page_content, request_human_intervention, request_human_intervention_sync,
    
    get_github_profile_tool, list_github_repos_tool, get_github_recent_activity_tool, list_github_commits_tool, list_github_branches_tool, get_github_file_content_tool, search_github_code_tool,
    # New Tools
    copy_to_clipboard_tool, paste_from_clipboard_tool, download_url_tool,
    download_email_attachment_tool, send_gmail_with_attachment_tool,
    download_classroom_materials_tool, submit_classroom_assignment_tool,
    schedule_delayed_task_tool, schedule_task_at_time_tool,
    list_scheduled_tasks_tool, cancel_scheduled_task_tool
)

# ==========================================
# TOOL GROUPINGS
# ==========================================

# --- Human Intervention Tool (Common) ---
human_intervention_tool = StructuredTool.from_function(
    func=request_human_intervention_sync,
    name="request_human_intervention",
    description="Pauses the automated process and requests manual intervention from the human user. Use this when you hit CAPTCHAs, bot checks, 2FA prompts, or roadblocks/issues you cannot solve yourself.",
    coroutine=request_human_intervention
)

# --- Memory ---
memory_tools = [
    StructuredTool.from_function(recall),
    StructuredTool.from_function(remember),
    human_intervention_tool
]

# --- Communication ---
gmail_tools = [
    StructuredTool.from_function(fetch_unread_mails),
    StructuredTool.from_function(send_gmail),
    StructuredTool.from_function(search_gmail),
    StructuredTool.from_function(read_gmail_msg),
    StructuredTool.from_function(trash_gmail_msg),
    StructuredTool.from_function(mark_gmail_read),
    StructuredTool.from_function(reply_to_gmail),
    StructuredTool.from_function(download_email_attachment_tool),
    StructuredTool.from_function(send_gmail_with_attachment_tool),
    human_intervention_tool
]


# --- Productivity ---
calendar_tools = [
    StructuredTool.from_function(add_google_task),
    StructuredTool.from_function(check_calendar_events),
    StructuredTool.from_function(add_calendar_event),
    human_intervention_tool
]

# --- Classroom ---
classroom_tools = [
    StructuredTool.from_function(fetch_classroom_courses),
    StructuredTool.from_function(fetch_classroom_assignments),
    StructuredTool.from_function(fetch_classroom_announcements),
    StructuredTool.from_function(fetch_classroom_assignment_details),
    StructuredTool.from_function(download_classroom_materials_tool),
    StructuredTool.from_function(submit_classroom_assignment_tool),
    human_intervention_tool
]

# --- System Info ---
system_info_tools = [
    StructuredTool.from_function(get_system_health),
    StructuredTool.from_function(get_weather),
    StructuredTool.from_function(get_time),
    StructuredTool.from_function(web_search),
    human_intervention_tool
]

# --- File Operations ---
file_management_tools = [
    StructuredTool.from_function(create_file_tool),
    StructuredTool.from_function(read_file_tool),
    StructuredTool.from_function(list_files_tool),
    StructuredTool.from_function(create_dir_tool),
    StructuredTool.from_function(save_code_tool),
    StructuredTool.from_function(index_directory_tool),
    StructuredTool.from_function(search_files_semantically_tool),
    StructuredTool.from_function(rag_file_qa_tool),
    human_intervention_tool
]

# --- System Control / Execution ---
system_control_tools = [
    StructuredTool.from_function(run_terminal_tool),
    StructuredTool.from_function(run_python_tool),
    StructuredTool.from_function(launch_app_tool),
    StructuredTool.from_function(get_audio_volume),
    StructuredTool.from_function(set_audio_volume),
    StructuredTool.from_function(mute_audio_toggle),
    StructuredTool.from_function(get_screen_brightness),
    StructuredTool.from_function(set_screen_brightness),
    StructuredTool.from_function(control_media_player),
    StructuredTool.from_function(list_running_processes_tool),
    StructuredTool.from_function(terminate_process_tool),
    StructuredTool.from_function(lock_desktop_screen),
    StructuredTool.from_function(suspend_desktop_system),
    StructuredTool.from_function(copy_to_clipboard_tool),
    StructuredTool.from_function(paste_from_clipboard_tool),
    StructuredTool.from_function(download_url_tool),
    StructuredTool.from_function(schedule_delayed_task_tool),
    StructuredTool.from_function(schedule_task_at_time_tool),
    StructuredTool.from_function(list_scheduled_tasks_tool),
    StructuredTool.from_function(cancel_scheduled_task_tool),
    human_intervention_tool
]

# --- Obsidian ---
obsidian_tools = [
    StructuredTool.from_function(create_obsidian_note),
    StructuredTool.from_function(append_to_obsidian_note),
    StructuredTool.from_function(search_obsidian_vault),
    StructuredTool.from_function(get_note_backlinks),
    StructuredTool.from_function(get_note_properties),
    StructuredTool.from_function(update_note_properties),
    StructuredTool.from_function(create_or_update_obsidian_canvas),
    human_intervention_tool
]

browser_tools = [
    StructuredTool.from_function(name="browser_navigate", description="Navigate to a URL and return interactive elements", coroutine=browser_navigate),
    StructuredTool.from_function(name="browser_click", description="Click an element by its numerical data-agent-id", coroutine=browser_click),
    StructuredTool.from_function(name="browser_click_selector", description="Click an element using a CSS/XPath selector", coroutine=browser_click_selector),
    StructuredTool.from_function(name="browser_input", description="Input text into an element by its numerical data-agent-id", coroutine=browser_input),
    StructuredTool.from_function(name="browser_input_selector", description="Input text into an element using a CSS/XPath selector", coroutine=browser_input_selector),
    StructuredTool.from_function(name="browser_go_back", description="Navigate back to the previous page", coroutine=browser_go_back),
    StructuredTool.from_function(name="browser_read_current_page", description="Read the current active tab's URL, page title, and interactive elements without navigating", coroutine=browser_read_current_page),
    StructuredTool.from_function(name="browser_read_page_content", description="Read or query the textual content (paragraphs, headings) of the current page in chunks or using a local LLM summary/query mode", coroutine=browser_read_page_content),
    human_intervention_tool,
]

# --- GitHub ---
github_tools = [
    StructuredTool.from_function(get_github_profile_tool, name="get_github_profile"),
    StructuredTool.from_function(list_github_repos_tool, name="list_github_repos"),
    StructuredTool.from_function(get_github_recent_activity_tool, name="get_github_recent_activity"),
    StructuredTool.from_function(list_github_commits_tool, name="list_github_commits"),
    StructuredTool.from_function(list_github_branches_tool, name="list_github_branches"),
    StructuredTool.from_function(get_github_file_content_tool, name="get_github_file_content"),
    StructuredTool.from_function(search_github_code_tool, name="search_github_code"),
    human_intervention_tool
]

# --- Miscellaneous ---
misc_tools = [
    StructuredTool.from_function(run_terminal_tool),
    StructuredTool.from_function(run_python_tool),
    StructuredTool.from_function(web_search),
    StructuredTool.from_function(read_file_tool),
    StructuredTool.from_function(create_file_tool),
    human_intervention_tool
]

# ==========================================
# EXPORTS
# ==========================================

# A dictionary for easy lookup by name if needed
TOOL_MAP = {
    # Browser Control
    "browser_navigate": browser_tools[0],
    "browser_click": browser_tools[1],
    "browser_click_selector": browser_tools[2],
    "browser_input": browser_tools[3],
    "browser_input_selector": browser_tools[4],
    "browser_go_back": browser_tools[5],
    "browser_read_current_page": browser_tools[6],
    "browser_read_page_content": browser_tools[7],
    "request_human_intervention": browser_tools[8],

    # Memory
    "recall": memory_tools[0],
    "remember": memory_tools[1],
    
    # Communication
    "fetch_unread_mails": gmail_tools[0],
    "send_gmail": gmail_tools[1],
    "search_gmail": gmail_tools[2],
    "read_gmail_msg": gmail_tools[3],
    "trash_gmail_msg": gmail_tools[4],
    "mark_gmail_read": gmail_tools[5],
    "reply_to_gmail": gmail_tools[6],

    # Productivity
    "add_google_task": calendar_tools[0],
    "check_calendar_events": calendar_tools[1],
    "add_calendar_event": calendar_tools[2],
    "fetch_classroom_courses": classroom_tools[0],
    "fetch_classroom_assignments": classroom_tools[1],
    "fetch_classroom_announcements": classroom_tools[2],
    "fetch_classroom_assignment_details": classroom_tools[3],

    # System Info
    "get_system_health": system_info_tools[0],
    "get_weather": system_info_tools[1],
    "get_time": system_info_tools[2],
    "web_search": system_info_tools[3],

    # File Ops
    "create_file_tool": file_management_tools[0],
    "read_file_tool": file_management_tools[1],
    "list_files_tool": file_management_tools[2],
    "create_dir_tool": file_management_tools[3],
    "save_code_tool": file_management_tools[4],
    "index_directory_tool": file_management_tools[5],
    "search_files_semantically_tool": file_management_tools[6],
    "rag_file_qa_tool": file_management_tools[7],

    # Execution
    "run_terminal_tool": system_control_tools[0],
    "run_python_tool": system_control_tools[1],
    "launch_app_tool": system_control_tools[2],
    "get_audio_volume": system_control_tools[3],
    "set_audio_volume": system_control_tools[4],
    "mute_audio_toggle": system_control_tools[5],
    "get_screen_brightness": system_control_tools[6],
    "set_screen_brightness": system_control_tools[7],
    "control_media_player": system_control_tools[8],
    "list_running_processes_tool": system_control_tools[9],
    "terminate_process_tool": system_control_tools[10],
    "lock_desktop_screen": system_control_tools[11],
    "suspend_desktop_system": system_control_tools[12],
    
    # Obsidian
    "create_obsidian_note": obsidian_tools[0],
    "append_to_obsidian_note": obsidian_tools[1],
    "search_obsidian_vault": obsidian_tools[2],
    "get_note_backlinks": obsidian_tools[3],
    "get_note_properties": obsidian_tools[4],
    "update_note_properties": obsidian_tools[5],
    "create_or_update_obsidian_canvas": obsidian_tools[6],

    # GitHub
    "get_github_profile": github_tools[0],
    "list_github_repos": github_tools[1],
    "get_github_recent_activity": github_tools[2],
    "list_github_commits": github_tools[3],
    "list_github_branches": github_tools[4],
    "get_github_file_content": github_tools[5],
    "search_github_code": github_tools[6]
}

# Consolidate all for the Supervisor or Generalist
ALL_TOOLS = (
    memory_tools + 
    gmail_tools + 
    calendar_tools + 
    classroom_tools + 
    system_info_tools + 
    file_management_tools + 
    system_control_tools +
    obsidian_tools +
    browser_tools +
    github_tools +
    misc_tools
)

