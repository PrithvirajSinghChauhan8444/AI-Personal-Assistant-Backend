
import subprocess
import os
import json
import sys


from AppOpener import open as open_app

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
    Launches an application.
    1. If arguments are provided (e.g. file path), use subprocess.
    2. If app_name is a path alias (e.g. 'projects'), use subprocess (explorer).
    3. Determine if we use AppOpener or Subprocess:
       - If no arguments and not a path alias: Use AppOpener for smart matching.
       - Else: Use subprocess (requires allowed_apps.json mapping).
    """
    # 1. Check for Path Aliases (treat as opening a folder/file directly without app name)
    resolved_path = resolve_path_alias(app_name)
    if resolved_path != app_name:
        # It was an alias! Treat it as "explorer <path>"
        try:
            cmd = ["explorer.exe", resolved_path]
            subprocess.Popen(cmd, shell=True)
            return f"🚀 Launched Path: {resolved_path}"
        except Exception as e:
            return f"❌ Error launching path: {e}"

    # 2. Hybrid Logic
    if not arguments:
        # --- AppOpener Mode ---
        # Logic: User said "open spotify", "open calculator"
        try:
            print(f"🤖 Application '{app_name}' launching via AppOpener...")
            # match_closest=True helps with 'calc' -> 'calculator', etc.
            open_app(app_name, match_closest=True, output=False) 
            return f"🚀 Launched (AppOpener): {app_name}"
        except Exception as e:
            return f"❌ AppOpener Failed: {e}"
    
    else:
        # --- Subprocess Mode (Files/Args) ---
        # Logic: User said "open notepad context.txt"
        apps = load_json_config("allowed_apps.json")
        executable = apps.get(app_name.lower())
        
        if not executable:
            # Fallback: try using the name as executable
            executable = app_name

        # Resolve arg alias
        real_arg = resolve_path_alias(arguments)
        cmd = [executable, real_arg]

        try:
            # Use Popen to launch without blocking (detached process)
            subprocess.Popen(cmd, shell=True)
            return f"🚀 Launched (Subprocess): {cmd}"
        except Exception as e:
            return f"❌ Error launching app: {e}"



launch_app("notepad", "context.txt")

