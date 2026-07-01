import sys
import builtins
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Infrastructure.auth_utils import verify_password
from src.CoreFunctions.Integrations.SystemControl.execution import run_python_script as _run_py

def run_python_tool(path: str) -> str:
    """Runs a python script at the specified path. PROTECTED.

    Args:
        path (str): The path to the Python file (.py) to execute.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: run_python_tool")
    print(f"   Args: path={path}")

    vis = getattr(builtins, "active_cli_visualizer", None)
    if vis and vis.active:
        vis.is_paused = True
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    if verify_password():
        try:
            res = _run_py(path)
            return res
        finally:
            if vis and vis.active:
                vis.is_paused = False
                
    if vis and vis.active:
        vis.is_paused = False
    return "❌ Action Cancelled: Incorrect Password."

run_python_tool_wrapped = StructuredTool.from_function(
    func=run_python_tool,
    name="run_python_tool",
    description="Runs a python script at the specified path. PROTECTED."
)
