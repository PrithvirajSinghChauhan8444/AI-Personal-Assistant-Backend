import subprocess
import os
import json
import sys
import platform
import shlex
from dotenv import load_dotenv
from CoreFunctions.security_utils import is_path_safe, is_command_safe

# Load environmental variables
load_dotenv()

open_app = None
if os.name == "nt":
    try:
        from AppOpener import open as open_app
    except Exception:
        open_app = None

# --- Helper to load JSON configs ---
def load_json_config(filename):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(current_dir, filename)
    if os.path.exists(path):
        # Try different encodings
        for encoding in ['utf-8', 'utf-16', 'utf-8-sig', 'cp1252']:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    return json.load(f)
            except UnicodeDecodeError:
                continue # Try next encoding
            except json.JSONDecodeError as e:
                print(f"❌ Error decoding JSON in {filename} ({encoding}): {e}")
                return {}
            except Exception as e:
                print(f"❌ Error loading {filename}: {e}")
                return {}
        
        print(f"❌ Failed to load {filename}: Could not determine encoding.")
        return {}
    return {}

def resolve_path_alias(path_or_alias):
    """
    Checks if the input matches a key in important_paths.json.
    If yes, returns the real path. If no, returns the input as-is.
    """
    paths = load_json_config("important_paths.json")
    # Check exact match (lowercase for case-insensitivity)
    return paths.get(path_or_alias.lower(), path_or_alias)


def run_terminal_command(command):
    """Executes a terminal command with live real-time output streaming. Protected by safety checks."""
    # Get working directory from AGENT_WORKSPACE
    agent_ws = os.getenv("AGENT_WORKSPACE")
    cwd = None
    if agent_ws:
        cwd = os.path.abspath(os.path.expanduser(agent_ws))
        os.makedirs(cwd, exist_ok=True)
    else:
        cwd = os.getcwd()

    if not is_command_safe(command, cwd=cwd):
        return f"❌ Security Violation: Terminal command execution blocked (contains prohibited command/pattern or accesses paths outside the allowed sandbox)."

    # Prepend virtual environment .venv/bin to PATH to enforce venv context and prevent system PEP 668 errors
    import copy
    sub_env = copy.deepcopy(os.environ)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    venv_bin = os.path.join(base_dir, ".venv", "bin")
    if os.path.exists(venv_bin):
        sub_env["PATH"] = venv_bin + os.pathsep + sub_env.get("PATH", "")
        sub_env["VIRTUAL_ENV"] = os.path.join(base_dir, ".venv")

    try:
        args = shlex.split(command)
        process = subprocess.Popen(
            args,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=cwd,
            env=sub_env
        )
        
        output_chunks = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                sys.stdout.write(line)
                sys.stdout.flush()
                output_chunks.append(line)
                
        process.wait()
        output = "".join(output_chunks)
        return f"Output:\n{output}"
    except Exception as e:
        return f"❌ Error executing command: {e}"

def run_python_script(path):
    """Executes a Python script in the current environment. Protected by sandbox validation."""
    real_path = resolve_path_alias(path)
    
    agent_ws = os.getenv("AGENT_WORKSPACE")
    if agent_ws and not os.path.isabs(real_path):
        abs_path = os.path.abspath(os.path.join(os.path.expanduser(agent_ws), real_path))
    else:
        abs_path = os.path.abspath(real_path)

    # Check path safety (sandboxing)
    if not is_path_safe(abs_path):
        return f"❌ Security Violation: Execution of script '{path}' is denied. Out of sandbox."

    if not os.path.exists(abs_path):
        return f"❌ Error: Script not found at {abs_path}"
    
    cwd = None
    if agent_ws:
        cwd = os.path.abspath(os.path.expanduser(agent_ws))
        os.makedirs(cwd, exist_ok=True)

    # Prepend virtual environment .venv/bin to PATH for consistency in nested script executions
    import copy
    sub_env = copy.deepcopy(os.environ)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    venv_bin = os.path.join(base_dir, ".venv", "bin")
    if os.path.exists(venv_bin):
        sub_env["PATH"] = venv_bin + os.pathsep + sub_env.get("PATH", "")
        sub_env["VIRTUAL_ENV"] = os.path.join(base_dir, ".venv")
    
    try:
        import sys
        process = subprocess.Popen(
            [sys.executable, abs_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=cwd,
            env=sub_env
        )
        
        output_chunks = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                sys.stdout.write(line)
                sys.stdout.flush()
                output_chunks.append(line)
                
        process.wait()
        output = "".join(output_chunks)
        return f"🐍 Script Output:\n{output}"
    except Exception as e:
        return f"❌ Error running script: {e}"


def launch_app(app_name, arguments=None):
    """
    Launches an application cross-platform.
    """
    is_windows = platform.system().lower() == "windows"
    resolved_path = resolve_path_alias(app_name)

    # 1. Handle Path Aliases (Folders/Files)
    if resolved_path != app_name:
        try:
            if is_windows:
                subprocess.Popen(["explorer.exe", resolved_path], shell=True)
            else:
                # Linux: xdg-open for folders/files
                subprocess.Popen(["xdg-open", resolved_path])
            return f"🚀 Launched Path: {resolved_path}"
        except Exception as e:
            return f"❌ Error launching path: {e}"

    # 2. Launch Application
    if not arguments:
        # --- App Launch (No args) ---
        if is_windows and open_app:
            try:
                open_app(app_name, match_closest=True, output=False)
                return f"🚀 Launched (AppOpener): {app_name}"
            except Exception:
                pass # Fallback to subprocess

        # Universal/Linux Subprocess Launch
        try:
            # On Linux/Unix, we try to run it as a detached process
            subprocess.Popen([app_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"🚀 Launched: {app_name}"
        except Exception as e:
            # Try searching in allowed_apps
            apps = load_json_config("allowed_apps.json")
            executable = apps.get(app_name.lower())
            if executable:
                try:
                    subprocess.Popen([executable])
                    return f"🚀 Launched (Config): {executable}"
                except Exception as e2:
                    return f"❌ Error: {e2}"
            return f"❌ Could not launch '{app_name}': {e}"
    
    else:
        # --- Launch with Arguments ---
        apps = load_json_config("allowed_apps.json")
        executable = apps.get(app_name.lower(), app_name)
        real_arg = resolve_path_alias(arguments)

        try:
            if is_windows:
                subprocess.Popen([executable, real_arg], shell=True)
            else:
                subprocess.Popen([executable, real_arg])
            return f"🚀 Launched: {executable} {real_arg}"
        except Exception as e:
            return f"❌ Error: {e}"
