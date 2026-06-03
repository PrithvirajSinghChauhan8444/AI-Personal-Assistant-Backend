
import os
import datetime
from CoreFunctions.security_utils import is_path_safe, is_extension_safe

def write_file(path, content):
    """
    Creates or overwrites a file with the specified content.
    Automatically creates parent directories. Protected by sandbox validation.
    """
    # 1. Resolve absolute path
    abs_path = os.path.abspath(path)
    
    # 2. Check path safety (sandboxing)
    if not is_path_safe(abs_path):
        return f"❌ Security Violation: Access to path '{path}' is denied. Out of sandbox."
        
    # 3. Check file extension safety
    if not is_extension_safe(abs_path):
        return f"❌ Security Violation: Writing to file '{path}' blocked (unsafe extension)."

    try:
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ File created successfully at: {abs_path}"
    except Exception as e:
        return f"❌ Error writing file: {e}"

def read_file(path):
    """Reads and returns the content of a file. Protected by sandbox validation."""
    abs_path = os.path.abspath(path)
    
    # Check path safety (sandboxing)
    if not is_path_safe(abs_path):
        return f"❌ Security Violation: Access to path '{path}' is denied. Out of sandbox."

    if not os.path.exists(abs_path):
        return f"❌ Error: File not found at {abs_path}"
    
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"❌ Error reading file: {e}"

def list_files(path):
    """Lists all files and folders in a specified directory. Protected by sandbox validation."""
    abs_path = os.path.abspath(path)
    
    # Check path safety (sandboxing)
    if not is_path_safe(abs_path):
        return f"❌ Security Violation: Access to path '{path}' is denied. Out of sandbox."

    if not os.path.exists(abs_path):
        return f"❌ Error: Path not found at {abs_path}"
    
    try:
        items = os.listdir(abs_path)
        if not items:
            return "Folder is empty."
        return "\n".join(items)
    except Exception as e:
        return f"❌ Error listing files: {e}"

def create_directory(path):
    """Creates a new folder. Protected by sandbox validation."""
    abs_path = os.path.abspath(path)
    
    # Check path safety (sandboxing)
    if not is_path_safe(abs_path):
        return f"❌ Security Violation: Access to path '{path}' is denied. Out of sandbox."

    try:
        os.makedirs(abs_path, exist_ok=True)
        return f"✅ Directory created: {abs_path}"
    except Exception as e:
        return f"❌ Error creating directory: {e}"

def save_python_code(content, suggested_name=None):
    """
    Saves Python code to a file inside CompiledScripts (within sandbox).
    """
    if not suggested_name:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested_name = f"generated_script_{timestamp}.py"
    
    # Ensure it ends with .py
    if not suggested_name.endswith('.py'):
        suggested_name += '.py'
        
    # Get base directory dynamically
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    save_dir = os.path.join(base_dir, "CompiledScripts")
    
    os.makedirs(save_dir, exist_ok=True)
    full_path = os.path.join(save_dir, suggested_name)
    
    return write_file(full_path, content)

