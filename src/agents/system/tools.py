"""Tool definitions for SystemAgent."""

from typing import List

from src.agents.contracts import ToolDefinition

SYSTEM_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="sys_exec",
        category="system",
        description="Executes an isolated Linux bash or shell command with a timeout deadline.",
        risk="HIGH",
        prompt_usage_tip="Use for terminal commands and running scripts. Specify cwd when executing within specific projects.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash or shell command to execute"},
                "timeout_seconds": {"type": "integer", "description": "Timeout in seconds (default: 30)", "default": 30},
                "cwd": {"type": "string", "description": "Working directory for the process"},
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
