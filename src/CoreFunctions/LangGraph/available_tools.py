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
    fetch_unread_mails, send_gmail,
    
    # Productivity
    add_google_task, check_calendar_events, add_calendar_event,
    
    # System info
    get_system_health, get_weather, get_time,
    
    # File Ops
    create_file_tool, read_file_tool, list_files_tool, 
    create_dir_tool, save_code_tool,
    
    # Execution
    run_terminal_tool, run_python_tool, launch_app_tool
)

# ==========================================
# TOOL GROUPINGS
# ==========================================

# --- Memory ---
memory_tools = [
    StructuredTool.from_function(recall),
    StructuredTool.from_function(remember),
]

# --- Communication ---
gmail_tools = [
    StructuredTool.from_function(fetch_unread_mails),
    StructuredTool.from_function(send_gmail),
]


# --- Productivity ---
calendar_tools = [
    StructuredTool.from_function(add_google_task),
    StructuredTool.from_function(check_calendar_events),
    StructuredTool.from_function(add_calendar_event),
]

# --- System Info ---
system_info_tools = [
    StructuredTool.from_function(get_system_health),
    StructuredTool.from_function(get_weather),
    StructuredTool.from_function(get_time),
]

# --- File Operations ---
file_management_tools = [
    StructuredTool.from_function(create_file_tool),
    StructuredTool.from_function(read_file_tool),
    StructuredTool.from_function(list_files_tool),
    StructuredTool.from_function(create_dir_tool),
    StructuredTool.from_function(save_code_tool),
]

# --- System Control / Execution ---
system_control_tools = [
    StructuredTool.from_function(run_terminal_tool),
    StructuredTool.from_function(run_python_tool),
    StructuredTool.from_function(launch_app_tool),
]

# ==========================================
# EXPORTS
# ==========================================

# A dictionary for easy lookup by name if needed
TOOL_MAP = {
    # Memory
    "recall": memory_tools[0],
    "remember": memory_tools[1],
    
    # Communication
    "fetch_unread_mails": gmail_tools[0],
    "send_gmail": gmail_tools[1],

    # Productivity
    "add_google_task": calendar_tools[0],
    "check_calendar_events": calendar_tools[1],
    "add_calendar_event": calendar_tools[2],

    # System Info
    "get_system_health": system_info_tools[0],
    "get_weather": system_info_tools[1],
    "get_time": system_info_tools[2],

    # File Ops
    "create_file_tool": file_management_tools[0],
    "read_file_tool": file_management_tools[1],
    "list_files_tool": file_management_tools[2],
    "create_dir_tool": file_management_tools[3],
    "save_code_tool": file_management_tools[4],

    # Execution
    "run_terminal_tool": system_control_tools[0],
    "run_python_tool": system_control_tools[1],
    "launch_app_tool": system_control_tools[2],
}

# Consolidate all for the Supervisor or Generalist
ALL_TOOLS = (
    memory_tools + 
    gmail_tools + 
    calendar_tools + 
    system_info_tools + 
    file_management_tools + 
    system_control_tools
)

