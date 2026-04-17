
import subprocess
import os
import json
import sys


import platform

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
    """Executes a shell command."""
    try:
        # Check if the command involves a path alias that needs resolving
        # Simple heuristic: split by space and check args? 
        # For now, let's keep it simple as aliases are mostly for arguments, 
        # but complex commands might be hard to parse here.
        
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout + result.stderr
        return f"Output:\n{output}"
    except Exception as e:
        return f"❌ Error executing command: {e}"

def run_python_script(path):
    """Executes a Python script in the current environment."""
    real_path = resolve_path_alias(path)
    
    if not os.path.exists(real_path):
        return f"❌ Error: Script not found at {real_path}"
    
    try:
        # Run using the same python interpreter
        result = subprocess.run([sys.executable, real_path], capture_output=True, text=True)
        output = result.stdout + result.stderr
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
