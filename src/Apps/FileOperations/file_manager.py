
import os
import datetime

def write_file(path, content):
    """
    Creates or overwrites a file with the specified content.
    Automatically creates parent directories.
    """
    try:
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ File created successfully at: {path}"
    except Exception as e:
        return f"❌ Error writing file: {e}"

def read_file(path):
    """Reads and returns the content of a file."""
    if not os.path.exists(path):
        return f"❌ Error: File not found at {path}"
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"❌ Error reading file: {e}"

def list_files(path):
    """Lists all files and folders in a specified directory."""
    if not os.path.exists(path):
        return f"❌ Error: Path not found at {path}"
    
    try:
        items = os.listdir(path)
        if not items:
            return "Folder is empty."
        return "\n".join(items)
    except Exception as e:
        return f"❌ Error listing files: {e}"

def create_directory(path):
    """Creates a new folder (and any necessary parent folders)."""
    try:
        os.makedirs(path, exist_ok=True)
        return f"✅ Directory created: {path}"
    except Exception as e:
        return f"❌ Error creating directory: {e}"

def save_python_code(content, suggested_name=None):
    """
    Saves Python code to a file.
    If suggested_name is not provided, generates a name based on timestamp.
    """
    if not suggested_name:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested_name = f"generated_script_{timestamp}.py"
    
    # Ensure it ends with .py
    if not suggested_name.endswith('.py'):
        suggested_name += '.py'
        
    # Default save location (can be customized)
    save_dir = "CompiledScripts" 
    os.makedirs(save_dir, exist_ok=True)
    
    full_path = os.path.join(save_dir, suggested_name)
    
    return write_file(full_path, content)
