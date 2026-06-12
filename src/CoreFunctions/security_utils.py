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
    r"\bpython\d*\s+-c\b",  # Inline python execution
    r"\bbash\s+-c\b",      # Inline bash execution
    r"\bsh\s+-c\b",        # Inline sh execution
    r"\beval\b",           # Eval command execution
    r"\|\s*(?:bash|sh|python)", # Piping commands to interpreters
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

def is_command_safe(command: str, cwd: str = None) -> bool:
    """
    Validates a shell command string against banned system command patterns
    and ensures that any path arguments in the command resolve to locations
    inside the whitelisted directories.
    """
    if not command:
        return False
        
    # 1. Check blocked command name/pattern
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return False
            
    # 2. Check path safety of arguments in command
    try:
        import shlex
        tokens = shlex.split(command)
    except Exception:
        tokens = command.split()
        
    for token in tokens:
        # Skip switches/options and URLs
        if token.startswith('-') or token.startswith('http://') or token.startswith('https://') or token.startswith('git@'):
            continue
            
        # Check if token represents a path candidate
        is_path_indicator = (
            '/' in token or 
            '\\' in token or 
            token.startswith('~') or 
            token.startswith('.') or
            re.search(r'\b(?:etc|var|usr|bin|opt|home|root|tmp|srv)\b', token)
        )
        
        if is_path_indicator:
            # Clean shell execution characters
            clean_token = token.strip('<>|&;`()$"\'')
            if not clean_token:
                continue
                
            # Expand user home directory
            expanded = os.path.expanduser(clean_token)
            
            # Resolve to absolute path
            if not os.path.isabs(expanded):
                if cwd:
                    abs_path = os.path.abspath(os.path.join(cwd, expanded))
                else:
                    abs_path = os.path.abspath(expanded)
            else:
                abs_path = os.path.abspath(expanded)
                
            # Enforce sandbox check on absolute path
            if not is_path_safe(abs_path):
                # Ensure it is a genuine path parameter
                if (
                    '/' in clean_token or 
                    '\\' in clean_token or 
                    clean_token.startswith('~') or 
                    clean_token.startswith('.') or 
                    os.path.exists(abs_path) or
                    clean_token.startswith(('/etc', '/home', '/var', '/usr', '/bin', '/tmp', '/opt', '/root'))
                ):
                    return False
                    
    return True
