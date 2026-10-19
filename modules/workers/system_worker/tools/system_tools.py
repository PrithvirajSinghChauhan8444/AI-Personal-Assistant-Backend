import os
import psutil
from langchain_core.tools import tool
from modules.infrastructure.security.vault import verify_password

@tool
def get_system_health() -> str:
    """Returns CPU, RAM, and Battery percentages."""
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()
    bat_str = f"{battery.percent}%" if battery else "N/A"
    return f"System Health: CPU: {cpu}%, RAM: {ram}%, Battery: {bat_str}"

@tool
def read_file_tool(file_path: str) -> str:
    """Reads content from a local file path."""
    if not os.path.exists(file_path):
        return f"Error: File '{file_path}' does not exist."
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

@tool
def create_file_tool(file_path: str, content: str) -> str:
    """Protected file creation tool. Requires system password authorization."""
    if not verify_password(f"Create or overwrite file at '{file_path}'"):
        return "Action aborted: Password verification failed or was cancelled."
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File '{file_path}' created successfully."
    except Exception as e:
        return f"Error writing file: {e}"

system_tools = [get_system_health, read_file_tool, create_file_tool]
