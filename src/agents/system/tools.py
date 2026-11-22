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
        prompt_usage_tip="Use for terminal commands and running scripts. Set detach=true for GUI apps or daemons. Destructive commands (rm -rf, git reset --hard) return confirmation_id requiring human approval.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash or shell command to execute"},
                "timeout_seconds": {"type": "integer", "description": "Timeout in seconds (default: 60)", "default": 60},
                "cwd": {"type": "string", "description": "Working directory for the process"},
                "detach": {"type": "boolean", "description": "Set to true to run GUI apps or background services detached without waiting", "default": False},
                "background": {"type": "boolean", "description": "Alias for detach", "default": False},
                "confirmation_id": {"type": "string", "description": "Confirmation token returned when a destructive command was challenged"},
                "log_file": {"type": "string", "description": "Optional custom log file path for detached command output"},
            },
            "required": ["command"],
        },
    ),
    # Tmux MCP Session & Terminal Management (tmux-mcp)
    ToolDefinition(
        name="tmux__list-sessions",
        category="mcp",
        description="List all active tmux sessions.",
        risk="LOW",
        prompt_usage_tip="Use to discover all running tmux sessions before interacting with a specific session.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="tmux__find-session",
        category="mcp",
        description="Find a tmux session by name.",
        risk="LOW",
        prompt_usage_tip="Use to check if a specific session name exists.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the tmux session to find"},
            },
            "required": ["name"],
        },
    ),
    ToolDefinition(
        name="tmux__list-windows",
        category="mcp",
        description="List windows in a tmux session.",
        risk="LOW",
        prompt_usage_tip="Use to inspect window IDs and titles within a tmux session.",
        parameters={
            "type": "object",
            "properties": {
                "sessionId": {"type": "string", "description": "ID of the tmux session"},
            },
            "required": ["sessionId"],
        },
    ),
    ToolDefinition(
        name="tmux__list-panes",
        category="mcp",
        description="List panes in a tmux window.",
        risk="LOW",
        prompt_usage_tip="Use to inspect active pane IDs in a window before sending commands or capturing output.",
        parameters={
            "type": "object",
            "properties": {
                "windowId": {"type": "string", "description": "ID of the tmux window"},
            },
            "required": ["windowId"],
        },
    ),
    ToolDefinition(
        name="tmux__capture-pane",
        category="mcp",
        description="Capture content from a tmux pane with configurable lines count and optional color preservation.",
        risk="LOW",
        prompt_usage_tip="Use to read terminal output or check logs and execution results inside a tmux pane.",
        parameters={
            "type": "object",
            "properties": {
                "paneId": {"type": "string", "description": "ID of the tmux pane"},
                "lines": {"type": "string", "description": "Number of lines to capture"},
                "colors": {"type": "boolean", "description": "Include color/escape sequences for text and background attributes in output"},
            },
            "required": ["paneId"],
        },
    ),
    ToolDefinition(
        name="tmux__create-session",
        category="mcp",
        description="Create a new tmux session.",
        risk="LOW",
        prompt_usage_tip="Use to spawn a new isolated persistent terminal session.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name for the new tmux session"},
            },
            "required": ["name"],
        },
    ),
    ToolDefinition(
        name="tmux__create-window",
        category="mcp",
        description="Create a new window in a tmux session.",
        risk="LOW",
        prompt_usage_tip="Use to create a dedicated window within an existing session.",
        parameters={
            "type": "object",
            "properties": {
                "sessionId": {"type": "string", "description": "ID of the tmux session"},
                "name": {"type": "string", "description": "Name for the new window"},
            },
            "required": ["sessionId", "name"],
        },
    ),
    ToolDefinition(
        name="tmux__kill-session",
        category="mcp",
        description="Kill a tmux session by ID.",
        risk="HIGH",
        prompt_usage_tip="Use to terminate and clean up a completed session.",
        parameters={
            "type": "object",
            "properties": {
                "sessionId": {"type": "string", "description": "ID of the tmux session to kill"},
            },
            "required": ["sessionId"],
        },
    ),
    ToolDefinition(
        name="tmux__kill-window",
        category="mcp",
        description="Kill a tmux window by ID.",
        risk="HIGH",
        prompt_usage_tip="Use to close a window by ID within a tmux session.",
        parameters={
            "type": "object",
            "properties": {
                "windowId": {"type": "string", "description": "ID of the tmux window to kill"},
            },
            "required": ["windowId"],
        },
    ),
    ToolDefinition(
        name="tmux__kill-pane",
        category="mcp",
        description="Kill a tmux pane by ID.",
        risk="HIGH",
        prompt_usage_tip="Use to terminate a specific pane within a window.",
        parameters={
            "type": "object",
            "properties": {
                "paneId": {"type": "string", "description": "ID of the tmux pane to kill"},
            },
            "required": ["paneId"],
        },
    ),
    ToolDefinition(
        name="tmux__split-pane",
        category="mcp",
        description="Split a tmux pane horizontally or vertically.",
        risk="MEDIUM",
        prompt_usage_tip="Use to split a pane for side-by-side or stacked terminal multitasking.",
        parameters={
            "type": "object",
            "properties": {
                "paneId": {"type": "string", "description": "ID of the tmux pane to split"},
                "direction": {"type": "string", "enum": ["horizontal", "vertical"], "description": "Split direction: 'horizontal' (side by side) or 'vertical' (top/bottom). Default is 'vertical'"},
                "size": {"type": "number", "minimum": 1, "maximum": 99, "description": "Size of the new pane as percentage (1-99). Default is 50%"},
            },
            "required": ["paneId"],
        },
    ),
    ToolDefinition(
        name="tmux__execute-command",
        category="mcp",
        description="Execute a command in a tmux pane and get results. For interactive applications (REPLs, editors), use rawMode=true. Avoid heredoc syntax (cat << EOF) when rawMode=false.",
        risk="MEDIUM",
        prompt_usage_tip="Use to run shell commands inside an existing tmux pane. Set rawMode=true for interactive REPLs or TUI apps.",
        parameters={
            "type": "object",
            "properties": {
                "paneId": {"type": "string", "description": "ID of the tmux pane"},
                "command": {"type": "string", "description": "Command to execute"},
                "rawMode": {"type": "boolean", "description": "Execute command without wrapper markers for REPL/interactive compatibility. Disables get-command-result status tracking. Use capture-pane after execution to verify command outcome."},
                "noEnter": {"type": "boolean", "description": "Send keystrokes without pressing Enter. For TUI navigation in apps like btop, vim, less. Supports special keys and strings. Automatically applies rawMode."},
            },
            "required": ["paneId", "command"],
        },
    ),
    ToolDefinition(
        name="tmux__get-command-result",
        category="mcp",
        description="Get the result of an executed command from tmux-mcp.",
        risk="LOW",
        prompt_usage_tip="Use to retrieve exit status and output for commands run with execute-command.",
        parameters={
            "type": "object",
            "properties": {
                "commandId": {"type": "string", "description": "ID of the executed command"},
            },
            "required": ["commandId"],
        },
    ),
    ToolDefinition(
        name="sys_process",
        category="system",
        description="Manages tracked background processes: list active jobs, inspect their output logs, or terminate them cleanly.",
        risk="LOW",
        prompt_usage_tip="Use to monitor background servers or GUI apps, inspect their live logs, or terminate them by PID.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "kill", "logs"], "description": "Action to perform"},
                "pid": {"type": "integer", "description": "Target process ID (required for kill and logs)"},
                "signal": {"type": "string", "enum": ["SIGTERM", "SIGKILL"], "description": "Signal to send (default: SIGTERM)", "default": "SIGTERM"},
                "lines": {"type": "integer", "description": "Number of trailing log lines to read (default: 50)", "default": 50},
            },
            "required": ["action"],
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

    # Hyprland Category
    ToolDefinition(
        name="hypr_get_active_window",
        category="hyprland",
        description="Gets the currently active/focused window in Hyprland with its title, class, address, workspace, pid, floating status, position, and size in JSON.",
        risk="LOW",
        prompt_usage_tip="Use to inspect what application or window the user is currently working on.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="hypr_get_workspaces",
        category="hyprland",
        description="Lists all active workspaces with their IDs, names, assigned monitors, window counts, and properties in JSON.",
        risk="LOW",
        prompt_usage_tip="Use to inspect workspace allocation, monitor assignments, and window distribution.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="hypr_get_clients",
        category="hyprland",
        description="Lists all open client windows across all workspaces in Hyprland with optional filtering by workspace, window class, or title.",
        risk="LOW",
        prompt_usage_tip="Use to find window addresses or locate where specific applications are open.",
        parameters={
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Optional filter by workspace name or ID (e.g. '1', '3', 'special:scratchpad')"},
                "class_name": {"type": "string", "description": "Optional case-insensitive filter by window class (e.g. 'firefox', 'code', 'kitty')"},
                "title": {"type": "string", "description": "Optional case-insensitive substring filter by window title"},
            },
        },
    ),
    ToolDefinition(
        name="hypr_get_monitors",
        category="hyprland",
        description="Lists all connected monitors/displays, their resolutions, refresh rates, active workspaces, and focus states in JSON.",
        risk="LOW",
        prompt_usage_tip="Use to inspect multi-monitor setups and display geometry.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="hypr_dispatch",
        category="hyprland",
        description="Executes a keybind dispatcher or command through hyprctl dispatch with arguments (supports classic dispatchers and Lua expressions).",
        risk="MEDIUM",
        prompt_usage_tip="Use for custom or raw Hyprland window manager dispatching actions.",
        parameters={
            "type": "object",
            "properties": {
                "dispatcher": {"type": "string", "description": "Dispatcher name (e.g. 'workspace', 'focuswindow', 'togglefloating', 'exec') or Lua expression ('hl.dsp.window.float()')"},
                "args": {"type": "string", "description": "Arguments for the dispatcher (e.g. '1', 'firefox', 'l')"},
            },
            "required": ["dispatcher"],
        },
    ),
    ToolDefinition(
        name="hypr_switch_workspace",
        category="hyprland",
        description="Switches the active workspace on the current monitor to a target workspace (by ID, name, or relative offset like '+1', '-1', 'special:scratchpad').",
        risk="LOW",
        prompt_usage_tip="Use when asked to navigate or switch to another desktop workspace.",
        parameters={
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Target workspace (e.g. '1', '2', 'work', '+1', '-1', 'special:scratchpad')"},
            },
            "required": ["workspace"],
        },
    ),
    ToolDefinition(
        name="hypr_move_window",
        category="hyprland",
        description="Moves a window to a target workspace or in a direction (l/r/u/d), with optional silent mode.",
        risk="MEDIUM",
        prompt_usage_tip="Use to move an application to another workspace or reposition it in the layout.",
        parameters={
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Target workspace ID or name (e.g. '3', 'special:scratchpad')"},
                "direction": {"type": "string", "description": "Direction to move window within layout: 'l', 'r', 'u', 'd'"},
                "silent": {"type": "boolean", "description": "Whether to move silently without following focus (default: false)"},
                "window": {"type": "string", "description": "Target window address or class regex (default: currently active window)"},
            },
        },
    ),
    ToolDefinition(
        name="hypr_focus_window",
        category="hyprland",
        description="Focuses a specific window by class, title regex, or address.",
        risk="LOW",
        prompt_usage_tip="Use to switch focus to a specific opened application.",
        parameters={
            "type": "object",
            "properties": {
                "window": {"type": "string", "description": "Window title, class regex, or address (e.g. 'firefox', 'code', 'address:0x...')"},
            },
            "required": ["window"],
        },
    ),
    ToolDefinition(
        name="hypr_window_action",
        category="hyprland",
        description="Performs layout and state actions on a window: toggle floating, fullscreen, pin, center, or move focus.",
        risk="MEDIUM",
        prompt_usage_tip="Use to float, fullscreen, pin, center, or navigate window focus.",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform: 'togglefloating', 'fullscreen', 'pin', 'center', 'cyclenext', 'movefocus_l', 'movefocus_r', 'movefocus_u', 'movefocus_d'",
                    "enum": ["togglefloating", "fullscreen", "pin", "center", "cyclenext", "movefocus_l", "movefocus_r", "movefocus_u", "movefocus_d"],
                },
                "window": {"type": "string", "description": "Optional target window address or class regex (default: active window)"},
            },
            "required": ["action"],
        },
    ),
    ToolDefinition(
        name="hypr_close_window",
        category="hyprland",
        description="Gracefully closes the active window or a specified window in Hyprland.",
        risk="HIGH",
        prompt_usage_tip="Use with caution. Confirm with user before closing working windows or tabs.",
        parameters={
            "type": "object",
            "properties": {
                "window": {"type": "string", "description": "Target window address or class regex (if omitted, closes the currently focused window)"},
            },
        },
    ),
    ToolDefinition(
        name="hypr_notify",
        category="hyprland",
        description="Sends a desktop notification directly through Hyprland's built-in notification system.",
        risk="LOW",
        prompt_usage_tip="Use to alert the user of finished tasks or status updates via on-screen Hyprland notification.",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Notification message to display"},
                "icon": {"type": "integer", "description": "Icon type: 0=Warning, 1=Info, 2=Hint, 3=Error, 4=Confused, 5=Ok, -1=None (default: 1)", "default": 1},
                "time_ms": {"type": "integer", "description": "Display duration in milliseconds (default: 3000)", "default": 3000},
                "color": {"type": "string", "description": "Notification color format (default: '0')", "default": "0"},
            },
            "required": ["message"],
        },
    ),
    ToolDefinition(
        name="hypr_keyword",
        category="hyprland",
        description="Sets a dynamic Hyprland config keyword (e.g. 'general:border_size 2') or forces a reload of the Hyprland configuration.",
        risk="MEDIUM",
        prompt_usage_tip="Use to tweak compositor visual settings dynamically or reload compositor rules.",
        parameters={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Keyword/setting name (e.g. 'general:border_size', 'animations:enabled', or 'reload')"},
                "value": {"type": "string", "description": "Value to set (if keyword is 'reload' or value is omitted, triggers config reload)"},
            },
            "required": ["keyword"],
        },
    ),
]
