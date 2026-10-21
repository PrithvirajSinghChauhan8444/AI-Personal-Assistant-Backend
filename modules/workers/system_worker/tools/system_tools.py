from typing import Optional, List
from langchain_core.tools import tool
from modules.workers.system_worker.integrations.system_client import (
    get_cpu_and_memory_health,
    read_local_file,
    write_local_file,
    list_local_directory,
    copy_clipboard_text,
    paste_clipboard_text,
    get_running_processes,
    launch_desktop_app,
    set_audio_volume
)
from modules.workers.system_worker.tools.media_tools import (
    control_spotify,
    control_youtube_music,
    control_system_media,
    media_tools
)

@tool
def get_system_health() -> str:
    """Returns CPU, RAM, and Battery percentages."""
    health = get_cpu_and_memory_health()
    return health.get("summary", "System Health OK")

@tool
def read_file_tool(file_path: str) -> str:
    """Reads content from a local file path."""
    return read_local_file(file_path)

@tool
def create_file_tool(file_path: str, content: str) -> str:
    """Protected file creation tool. Requires system password authorization."""
    return write_local_file(file_path, content)

@tool
def list_files_tool(directory_path: str = ".") -> str:
    """Lists files and directories in the specified path."""
    entries = list_local_directory(directory_path)
    if not entries:
        return f"Directory '{directory_path}' is empty or does not exist."
    return f"Files in '{directory_path}':\n" + "\n".join(f"- {e}" for e in entries[:100])

@tool
def copy_to_clipboard_tool(text: str) -> str:
    """Copies text to the system clipboard."""
    return copy_clipboard_text(text)

@tool
def paste_from_clipboard_tool() -> str:
    """Reads text from the system clipboard."""
    return paste_clipboard_text()

@tool
def list_running_processes_tool(limit: int = 15) -> str:
    """Lists currently running system processes sorted by memory usage."""
    procs = get_running_processes(limit)
    lines = [f"Top {len(procs)} Running Processes:"]
    for p in procs:
        lines.append(f"PID {p['pid']}: {p['name']} | CPU: {p['cpu_percent']}% | RAM: {p['memory_percent']:.1f}%")
    return "\n".join(lines)

@tool
def launch_application_tool(app_name: str) -> str:
    """Launches an installed desktop application by name (e.g. 'spotify', 'chrome', 'firefox', 'vlc')."""
    return launch_desktop_app(app_name)

@tool
def set_system_volume_tool(volume_percent: int) -> str:
    """Sets system output audio volume percentage (0-100)."""
    return set_audio_volume(volume_percent)

system_tools = [
    get_system_health,
    read_file_tool,
    create_file_tool,
    list_files_tool,
    copy_to_clipboard_tool,
    paste_from_clipboard_tool,
    list_running_processes_tool,
    launch_application_tool,
    set_system_volume_tool,
    *media_tools
]
