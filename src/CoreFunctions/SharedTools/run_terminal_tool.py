import re
import sys
import builtins
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Infrastructure.auth_utils import verify_password
from src.CoreFunctions.Integrations.SystemControl.execution import run_terminal_command as _run_term

def run_terminal_tool(command: str) -> str:
    """Runs a bash terminal command. PROTECTED.

    Args:
        command (str): The exact shell command string to execute.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: run_terminal_tool")
    print(f"   Args: command={command}")
    
    if re.search(r'\bsleep\b', command.lower()):
        return "❌ Error: Synchronous 'sleep' or delay commands are strictly prohibited in run_cmd to prevent terminal freeze. To run tasks at a future time or schedule a reminder, you MUST use `schedule_delayed_task` or `schedule_task_at_time` instead."
    
    vis = getattr(builtins, "active_cli_visualizer", None)
    if vis and vis.active:
        vis.is_paused = True
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    if verify_password():
        try:
            res = _run_term(command)
            return res
        finally:
            if vis and vis.active:
                vis.is_paused = False
    
    if vis and vis.active:
        vis.is_paused = False
    return "❌ Action Cancelled: Incorrect Password."

run_terminal_tool_wrapped = StructuredTool.from_function(
    func=run_terminal_tool,
    name="run_terminal_tool",
    description="Runs a bash terminal command. PROTECTED."
)
