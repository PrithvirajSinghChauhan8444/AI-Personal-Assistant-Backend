"""Tool definitions for SystemAgent."""

from typing import List

from src.agents.contracts import ToolDefinition

SYSTEM_TOOLS: List[ToolDefinition] = [
    # Process & Execution
    ToolDefinition(
        name="sys_exec",
        category="system",
        description="Executes a Linux bash or shell command with a timeout deadline, or launches background/GUI processes detached.",
        risk="HIGH",
        prompt_usage_tip="Use for terminal commands and running scripts. For continuous services, daemons, or GUI apps (e.g. steam, browsers), set background=true so they run detached without blocking.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash or shell command to execute"},
                "timeout_seconds": {"type": "integer", "description": "Timeout in seconds (default: 30)", "default": 30},
                "cwd": {"type": "string", "description": "Working directory for the process"},
                "background": {"type": "boolean", "description": "Set to true to run long-running daemons, services, or GUI apps detached in the background without waiting", "default": False},
                "log_file": {"type": "string", "description": "Optional custom log file path for background command output"},
            },
            "required": ["command"],
        },
    ),
    ToolDefinition(
        name="sys_ps",
        category="system",
        description="Lists active operating system processes, memory usage, CPU, and PIDs.",
        risk="LOW",
        prompt_usage_tip="Use to inspect background jobs, resource utilization, or find PIDs for sys_kill.",
        parameters={
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "Optional process name or command filter"},
                "limit": {"type": "integer", "description": "Maximum number of processes to return (default: 50)", "default": 50},
            },
        },
    ),
    ToolDefinition(
        name="sys_kill",
        category="system",
        description="Terminates a process by PID with a specified signal (SIGTERM, SIGKILL).",
        risk="HIGH",
        prompt_usage_tip="Attempt graceful SIGTERM before forceful SIGKILL.",
        parameters={
            "type": "object",
            "properties": {
                "pid": {"type": "integer", "description": "Process ID to terminate"},
                "signal": {"type": "string", "description": "Signal: SIGTERM, SIGKILL, SIGHUP, SIGINT (default: SIGTERM)", "default": "SIGTERM"},
            },
            "required": ["pid"],
        },
    ),
    ToolDefinition(
        name="sys_exec_python",
        category="system",
        description="Executes an ephemeral Python script safely in a subprocess and returns stdout/stderr.",
        risk="HIGH",
        prompt_usage_tip="Use for mathematical computation, data processing, or rapid verification.",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source code to execute"},
                "timeout_seconds": {"type": "integer", "description": "Timeout in seconds (default: 30)", "default": 30},
            },
            "required": ["code"],
        },
    ),

    # Hardware & Audio Controls
    ToolDefinition(
        name="sys_volume_get",
        category="system",
        description="Gets the current system audio volume percentage and mute status.",
        risk="LOW",
        prompt_usage_tip="Use to inspect current audio volume and mute state.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="sys_volume_set",
        category="system",
        description="Sets the system audio volume to a specific percentage (0-100).",
        risk="LOW",
        prompt_usage_tip="Use to adjust speaker or headphone volume.",
        parameters={
            "type": "object",
            "properties": {
                "level": {"type": "integer", "description": "Target volume percentage (0 to 100)"},
            },
            "required": ["level"],
        },
    ),
    ToolDefinition(
        name="sys_volume_mute",
        category="system",
        description="Toggles system audio mute state on or off.",
        risk="LOW",
        prompt_usage_tip="Use to silence or unsilence sound.",
        parameters={"type": "object", "properties": {}},
    ),

    # Display Controls
    ToolDefinition(
        name="sys_brightness_get",
        category="system",
        description="Gets the current screen brightness percentage.",
        risk="LOW",
        prompt_usage_tip="Use to inspect display brightness level.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="sys_brightness_set",
        category="system",
        description="Sets the screen brightness to a specific percentage (1-100).",
        risk="LOW",
        prompt_usage_tip="Use to adjust screen backlight intensity.",
        parameters={
            "type": "object",
            "properties": {
                "level": {"type": "integer", "description": "Target brightness percentage (1 to 100)"},
            },
            "required": ["level"],
        },
    ),

    # Desktop State, Power & Diagnostics
    ToolDefinition(
        name="sys_lock",
        category="system",
        description="Locks the active desktop session using the desktop lock screen.",
        risk="MEDIUM",
        prompt_usage_tip="Use when the user requests locking the screen.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="sys_suspend",
        category="system",
        description="Suspends the system into low-power sleep state (suspend to RAM).",
        risk="HIGH",
        prompt_usage_tip="Requires explicit confirmation before putting the system to sleep.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="sys_health",
        category="system",
        description="Reports real-time system health including CPU usage, RAM utilization, root disk space, and battery status.",
        risk="LOW",
        prompt_usage_tip="Use to check resource utilization, memory limits, or battery level.",
        parameters={"type": "object", "properties": {}},
    ),

    # Clipboard & Launcher
    ToolDefinition(
        name="sys_clipboard_copy",
        category="system",
        description="Copies text to the system clipboard using Wayland (wl-copy) or X11 (xclip/xsel).",
        risk="LOW",
        prompt_usage_tip="Use when asked to copy text, links, or code for the user.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to place into system clipboard"},
            },
            "required": ["text"],
        },
    ),
    ToolDefinition(
        name="sys_clipboard_paste",
        category="system",
        description="Retrieves and returns text content from the system clipboard.",
        risk="LOW",
        prompt_usage_tip="Use to inspect what the user currently has copied.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="sys_launch_app",
        category="system",
        description="Launches an application, URI, or directory path detached on the desktop session.",
        risk="MEDIUM",
        prompt_usage_tip="Use to open GUI apps, browser, editor, or folder targets.",
        parameters={
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name or path (e.g. 'code', 'firefox', 'vlc', or directory)"},
                "arguments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional CLI arguments or file targets",
                },
            },
            "required": ["app_name"],
        },
    ),
    ToolDefinition(
        name="sys_get_time",
        category="system",
        description="Returns the current system timestamp in both local time and UTC.",
        risk="LOW",
        prompt_usage_tip="Use to check exact date, time, weekday, or timezone.",
        parameters={"type": "object", "properties": {}},
    ),

    # Filesystem Category
    ToolDefinition(
        name="fs_read",
        category="filesystem",
        description="Reads UTF-8 text from disk with line and byte slicing options.",
        risk="LOW",
        prompt_usage_tip="Use start_line and end_line for targeted inspection of large files.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
                "start_line": {"type": "integer", "description": "1-based starting line number (inclusive)"},
                "end_line": {"type": "integer", "description": "1-based ending line number (inclusive)"},
                "byte_offset": {"type": "integer", "description": "Byte offset into the file"},
                "length_bytes": {"type": "integer", "description": "Maximum bytes to read"},
            },
            "required": ["path"],
        },
    ),
    ToolDefinition(
        name="fs_write",
        category="filesystem",
        description="Writes or overwrites a file atomically via tempfile replacement, or appends.",
        risk="MEDIUM",
        prompt_usage_tip="Creates missing parent directories automatically.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path"},
                "content": {"type": "string", "description": "Text content to write"},
                "append": {"type": "boolean", "description": "Whether to append rather than overwrite"},
            },
            "required": ["path", "content"],
        },
    ),
    ToolDefinition(
        name="fs_delete",
        category="filesystem",
        description="Deletes a file or directory on disk (high risk operation).",
        risk="HIGH",
        prompt_usage_tip="Use with caution. Deletions trigger human authorization prompts.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to delete"},
                "recursive": {"type": "boolean", "description": "Set true to recursively remove directories"},
            },
            "required": ["path"],
        },
    ),
    ToolDefinition(
        name="fs_list",
        category="filesystem",
        description="Lists files and directories with sizes, timestamps, and tree traversal options.",
        risk="LOW",
        prompt_usage_tip="Use to inspect project layouts and verify folder structures.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list (default: .)"},
                "recursive": {"type": "boolean", "description": "Recursively traverse subdirectories"},
                "max_depth": {"type": "integer", "description": "Maximum recursion depth (default: 2)"},
            },
        },
    ),
    ToolDefinition(
        name="fs_ripgrep",
        category="filesystem",
        description="High-speed regex and text search across files and directories.",
        risk="LOW",
        prompt_usage_tip="Use to locate functions, variables, errors, or keywords across the codebase.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Regex or text string to search for"},
                "path": {"type": "string", "description": "Directory or file to search within (default: .)"},
                "file_pattern": {"type": "string", "description": "Glob pattern filtering file names (e.g. *.py)"},
                "case_sensitive": {"type": "boolean", "description": "Whether search is case-sensitive"},
                "max_matches": {"type": "integer", "description": "Maximum matches to return (default: 100)"},
            },
            "required": ["query"],
        },
    ),

    # Git Category
    ToolDefinition(
        name="git_status",
        category="git",
        description="Returns current Git branch, tracking status, staged, and unstaged modifications.",
        risk="LOW",
        prompt_usage_tip="Use before committing or reviewing repository changes.",
        parameters={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Target git repository directory (default: .)"},
            },
        },
    ),
    ToolDefinition(
        name="git_diff",
        category="git",
        description="Returns unified diff against working directory, staged changes, or a target branch/commit.",
        risk="LOW",
        prompt_usage_tip="Use to review modifications before creating commits.",
        parameters={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Target git repository directory (default: .)"},
                "target": {"type": "string", "description": "Commit or ref to diff against (e.g. HEAD)"},
                "staged": {"type": "boolean", "description": "Set true to diff staged changes"},
            },
        },
    ),
    ToolDefinition(
        name="git_commit",
        category="git",
        description="Stages files and creates a Git commit with a structured commit message.",
        risk="MEDIUM",
        prompt_usage_tip="Follow conventional commit guidelines (feat, fix, refactor, docs).",
        parameters={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Target git repository directory (default: .)"},
                "message": {"type": "string", "description": "Git commit message"},
                "files": {"type": "array", "items": {"type": "string"}, "description": "Files to stage (default: all)"},
            },
            "required": ["message"],
        },
    ),
]
