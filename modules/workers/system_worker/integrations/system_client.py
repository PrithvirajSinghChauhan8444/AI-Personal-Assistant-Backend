import os
import psutil
from typing import Dict, Any, List
from modules.infrastructure.security.vault import verify_password

def get_cpu_and_memory_health() -> Dict[str, Any]:
    """Calculates CPU, virtual memory, and battery statistics."""
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()
    bat_str = f"{battery.percent}%" if battery else "N/A"
    return {
        "cpu_percent": cpu,
        "ram_percent": ram,
        "battery": bat_str,
        "summary": f"System Health: CPU: {cpu}%, RAM: {ram}%, Battery: {bat_str}"
    }

def read_local_file(file_path: str) -> str:
    """Reads content from a local file path."""
    if not os.path.exists(file_path):
        return f"Error: File '{file_path}' does not exist."
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_local_file(file_path: str, content: str) -> str:
    """Writes content to a file. Prompts for security vault verification."""
    if not verify_password(f"Create or overwrite file at '{file_path}'"):
        return "Action aborted: Password verification failed or was cancelled."
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File '{file_path}' created successfully."
    except Exception as e:
        return f"Error writing file: {e}"

def list_local_directory(directory_path: str = ".") -> List[str]:
    """Lists files and directories in path."""
    if not os.path.exists(directory_path):
        return []
    return sorted(os.listdir(directory_path))

def copy_clipboard_text(text: str) -> str:
    """Copies text to system clipboard."""
    try:
        from src.CoreFunctions.Integrations.System.clipboard_ops import copy_to_clipboard
        return copy_to_clipboard(text)
    except Exception:
        import subprocess
        proc = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
        proc.communicate(text.encode('utf-8'))
        return "Copied to clipboard."

def paste_clipboard_text() -> str:
    """Pastes text from system clipboard."""
    try:
        from src.CoreFunctions.Integrations.System.clipboard_ops import paste_from_clipboard
        return paste_from_clipboard()
    except Exception:
        import subprocess
        return subprocess.check_output(['xclip', '-selection', 'clipboard', '-o']).decode('utf-8')

def get_running_processes(limit: int = 15) -> List[Dict[str, Any]]:
    """Retrieves top running processes sorted by RAM usage."""
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x.get('memory_percent') or 0, reverse=True)
    return procs[:limit]

def launch_desktop_app(app_name: str) -> str:
    """Launches an application."""
    from src.CoreFunctions.Integrations.SystemControl.execution import launch_app
    return launch_app(app_name)

def set_audio_volume(volume_percent: int) -> str:
    """Sets system audio volume percentage (0-100)."""
    from src.CoreFunctions.Integrations.System.system_actions import set_volume
    return set_volume(volume_percent)
