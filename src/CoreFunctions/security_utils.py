import os
import re
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()

# Base directory of the repository
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Whitelisted directories that the agent is allowed to access
ALLOWED_DIRECTORIES = [
    os.path.realpath(BASE_DIR),
    os.path.realpath(os.environ.get("OBSIDIAN_VAULT_PATH", "/home/prit/Documents/Obsidian Vaultt")),
]

agent_ws = os.getenv("AGENT_WORKSPACE")
if agent_ws:
    resolved_ws = os.path.realpath(os.path.expanduser(agent_ws))
    os.makedirs(resolved_ws, exist_ok=True)
    if resolved_ws not in ALLOWED_DIRECTORIES:
        ALLOWED_DIRECTORIES.append(resolved_ws)

BLOCKED_COMMAND_PATTERNS = [
    r"\brm\b",          # Remove files (potentially destructive)
    r"\bsudo\b",        # Superuser command execution
    r"\bchmod\b",       # Change file permissions
    r"\bchown\b",       # Change file owner
    r"\bdd\b",          # Low-level copying and formatting
    r"\bshutdown\b",    # Shut down system
    r"\breboot\b",      # Reboot system
    r"\bpasswd\b",      # Change passwords
    r"\bmv\s+(?:/[a-zA-Z0-9_\-\.]+)+",  # Moving system directories
]

BLOCKED_EXTENSIONS = {
    ".sh", ".bash", ".zsh", ".exe", ".bin", ".elf", ".bat", ".cmd"
}

def is_path_safe(target_path: str) -> bool:
    """
    Validates if a target path resides strictly inside the whitelisted directories.
    Resolves symlinks, relative components, and checks boundaries to prevent path traversal attacks.
    """
    if not target_path:
        return False
        
    try:
        # Resolve path completely to get absolute canonical path (resolves symlinks and ..)
        canonical_path = os.path.realpath(target_path)
        
        # Check against allowed directories
        for allowed_dir in ALLOWED_DIRECTORIES:
            # Ensure allowed_dir path ends with a separator to prevent partial folder matches
            # e.g., '/path/to/project_dir_extra' shouldn't match '/path/to/project_dir'
            prefix = os.path.join(allowed_dir, '')
            if canonical_path.startswith(prefix) or canonical_path == allowed_dir:
                return True
        return False
    except Exception:
        return False

def is_extension_safe(filepath: str) -> bool:
    """
    Ensures that the file extension is not in the blocked executable extensions.
    """
    _, ext = os.path.splitext(filepath)
    return ext.lower() not in BLOCKED_EXTENSIONS

def is_command_safe(command: str) -> bool:
    """
    Validates a shell command string against banned system command patterns.
    """
    if not command:
        return False
        
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return False
    return True
