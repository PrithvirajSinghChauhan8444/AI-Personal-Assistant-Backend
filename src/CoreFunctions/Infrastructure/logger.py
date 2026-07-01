import os
import json
import sys
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

# Global lock for thread safety
_log_lock = threading.Lock()

# Thread-local storage to hold the session_id for the current thread
_session_context = threading.local()

# Global registry of active sessions to allow multi-threaded access
_active_sessions = {}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS_DIR = os.path.join(BASE_DIR, "Memory", "logs")

def set_thread_session_id(session_id: str):
    """Sets the session ID for the current thread."""
    _session_context.session_id = session_id

def get_current_session_id() -> Optional[str]:
    """Retrieves the session ID for the current thread."""
    return getattr(_session_context, "session_id", None)

def _get_active_session_val(key: str) -> Any:
    """Helper to fetch a value from the current active session registry."""
    sid = get_current_session_id()
    if sid and sid in _active_sessions:
        return _active_sessions[sid].get(key)
    return None

def _set_active_session_val(key: str, value: Any):
    """Helper to write/update a value in the current active session registry."""
    sid = get_current_session_id()
    if sid:
        if sid not in _active_sessions:
            _active_sessions[sid] = {}
        _active_sessions[sid][key] = value

def init_session_logger(session_id: str, primary_goal: str = ""):
    """Initializes the session logger and sets up context for the current thread."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    with _log_lock:
        # Bind session_id to current thread
        set_thread_session_id(session_id)
        
        # Build session record
        session_info = {
            "trace": {
                "session_id": session_id,
                "timestamp_start": datetime.now().isoformat(),
                "primary_goal": primary_goal,
                "steps": [],
                "timestamp_end": None,
                "final_response": None,
                "success": True,
                "errors": []
            },
            "text_log_path": os.path.join(LOGS_DIR, f"session_{session_id}.log"),
            "json_log_path": os.path.join(LOGS_DIR, f"session_{session_id}.json"),
            "latest_text_path": os.path.join(LOGS_DIR, "latest.log"),
            "latest_json_path": os.path.join(LOGS_DIR, "latest.json")
        }
        _active_sessions[session_id] = session_info
        
        # Write initial session header to the log file
        header = (
            f"{'='*80}\n"
            f"SESSION START: {session_id} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Primary Goal: {primary_goal}\n"
            f"{'='*80}\n\n"
        )
        
        _write_text(header, overwrite=True)
        _write_json()

def _write_text(content: str, overwrite: bool = False):
    """Internal helper to write text logs to both session and latest files."""
    mode = "w" if overwrite else "a"
    text_log_path = _get_active_session_val("text_log_path")
    latest_text_path = _get_active_session_val("latest_text_path")
    
    try:
        if text_log_path:
            with open(text_log_path, mode, encoding="utf-8") as f:
                f.write(content)
        if latest_text_path:
            with open(latest_text_path, mode, encoding="utf-8") as f:
                f.write(content)
    except Exception as e:
        sys.stderr.write(f"Logging write failure: {e}\n")

def _write_json():
    """Internal helper to dump the current JSON trace to both session and latest files."""
    trace_data = _get_active_session_val("trace")
    json_log_path = _get_active_session_val("json_log_path")
    latest_json_path = _get_active_session_val("latest_json_path")
    
    if not trace_data:
        return
        
    try:
        if json_log_path:
            with open(json_log_path, "w", encoding="utf-8") as f:
                json.dump(trace_data, f, indent=4)
        if latest_json_path:
            with open(latest_json_path, "w", encoding="utf-8") as f:
                json.dump(trace_data, f, indent=4)
    except Exception as e:
        sys.stderr.write(f"Logging JSON dump failure: {e}\n")

def log_message(message: str):
    """Logs a general informational message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    log_line = f"[{timestamp}] {message}\n"
    with _log_lock:
        _write_text(log_line)

def log_node_start(node_name: str, input_state: Dict[str, Any]):
    """Logs the entry into a StateGraph node."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    header = f"\n[Node: {node_name} Start] ({timestamp})\n"
    
    sanitized_input = _sanitize_state(input_state)
    input_str = json.dumps(sanitized_input, indent=2)
    
    with _log_lock:
        _write_text(f"{header}Input State:\n{input_str}\n")
        
        trace = _get_active_session_val("trace")
        if trace:
            trace["steps"].append({
                "type": "node_execution",
                "name": node_name,
                "timestamp_start": datetime.now().isoformat(),
                "input": sanitized_input,
                "output": None,
                "timestamp_end": None
            })
            _write_json()

def log_node_end(node_name: str, output_state: Dict[str, Any]):
    """Logs the output and exit from a StateGraph node."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sanitized_output = _sanitize_state(output_state)
    output_str = json.dumps(sanitized_output, indent=2)
    
    log_block = (
        f"Output Update:\n{output_str}\n"
        f"--- Node {node_name} Finished ({timestamp}) ---\n\n"
    )
    
    with _log_lock:
        _write_text(log_block)
        
        trace = _get_active_session_val("trace")
        if trace:
            for step in reversed(trace["steps"]):
                if step["type"] == "node_execution" and step["name"] == node_name and step["timestamp_end"] is None:
                    step["output"] = sanitized_output
                    step["timestamp_end"] = datetime.now().isoformat()
                    break
            _write_json()

def log_worker_start(worker_name: str, task_description: str, model_name: str, prompt_context: str):
    """Logs the initialization of an isolated worker run."""
    with _log_lock:
        banner = (
            f"  ----------------------------------------------------------------------\n"
            f"  🚀 [Worker Start: {worker_name}] Using Model: {model_name}\n"
            f"  Task: {task_description}\n"
            f"  ----------------------------------------------------------------------\n"
            f"  Prompt:\n  {_indent_text(prompt_context, 2)}\n"
            f"  ----------------------------------------------------------------------\n"
        )
        _write_text(banner)
        
        trace = _get_active_session_val("trace")
        if trace:
            trace["steps"].append({
                "type": "worker_run",
                "worker": worker_name,
                "model": model_name,
                "task": task_description,
                "prompt": prompt_context,
                "events": [],
                "final_output": None,
                "timestamp_start": datetime.now().isoformat(),
                "timestamp_end": None
            })
            _write_json()

def log_worker_thought(worker_name: str, thought: str):
    """Logs intermediate reasoning/thoughts of a worker."""
    with _log_lock:
        log_line = f"  🤔 [{worker_name} Thought]:\n  {_indent_text(thought, 4)}\n"
        _write_text(log_line)
        
        trace = _get_active_session_val("trace")
        if trace:
            worker_step = _get_active_worker_step(trace, worker_name)
            if worker_step:
                worker_step["events"].append({
                    "type": "thought",
                    "timestamp": datetime.now().isoformat(),
                    "content": thought
                })
                _write_json()

def log_worker_tool_call(worker_name: str, tool_name: str, args: Dict[str, Any]):
    """Logs when a worker invokes a specific tool."""
    args_str = json.dumps(args, indent=2)
    with _log_lock:
        log_block = (
            f"  🔍 [{worker_name}] Tool Call: {tool_name}\n"
            f"     Arguments:\n{_indent_text(args_str, 5)}\n"
        )
        _write_text(log_block)
        
        trace = _get_active_session_val("trace")
        if trace:
            worker_step = _get_active_worker_step(trace, worker_name)
            if worker_step:
                worker_step["events"].append({
                    "type": "tool_call",
                    "tool_name": tool_name,
                    "arguments": args,
                    "timestamp_start": datetime.now().isoformat(),
                    "response": None,
                    "timestamp_end": None
                })
                _write_json()

def log_worker_tool_response(worker_name: str, tool_name: str, response: str):
    """Logs the raw return values from a tool execution."""
    text_resp = response
    if len(text_resp) > 3000:
        text_resp = text_resp[:3000] + "\n... (truncated for readability)"
        
    with _log_lock:
        log_block = f"  📥 [{worker_name}] Tool {tool_name} returned:\n{_indent_text(text_resp, 5)}\n"
        _write_text(log_block)
        
        trace = _get_active_session_val("trace")
        if trace:
            worker_step = _get_active_worker_step(trace, worker_name)
            if worker_step:
                for event in reversed(worker_step["events"]):
                    if event["type"] == "tool_call" and event["tool_name"] == tool_name and event["timestamp_end"] is None:
                        event["response"] = response
                        event["timestamp_end"] = datetime.now().isoformat()
                        break
                _write_json()

def log_worker_end(worker_name: str, final_output: str):
    """Logs the completion of a worker agent run."""
    with _log_lock:
        banner = (
            f"  ----------------------------------------------------------------------\n"
            f"  ✔ [Worker End: {worker_name}] Completed task successfully.\n"
            f"  Final Output:\n  {_indent_text(final_output, 2)}\n"
            f"  ----------------------------------------------------------------------\n"
        )
        _write_text(banner)
        
        trace = _get_active_session_val("trace")
        if trace:
            worker_step = _get_active_worker_step(trace, worker_name)
            if worker_step:
                worker_step["final_output"] = final_output
                worker_step["timestamp_end"] = datetime.now().isoformat()
                _write_json()

def log_error(source: str, message: str, details: str = ""):
    """Logs execution failures or exceptions."""
    log_block = f"❌ ERROR in [{source}]: {message}\n"
    if details:
        log_block += f"Details:\n{_indent_text(details, 2)}\n"
        
    with _log_lock:
        _write_text(log_block)
        
        trace = _get_active_session_val("trace")
        if trace:
            trace["success"] = False
            trace["errors"].append({
                "source": source,
                "message": message,
                "details": details,
                "timestamp": datetime.now().isoformat()
            })
            _write_json()

def end_session_logger(final_response: str, success: bool = True):
    """Completes the session trace and writes the footer to the log file."""
    sid = get_current_session_id()
    if not sid:
        return
        
    footer = (
        f"\n{'='*80}\n"
        f"SESSION END: {sid} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Success: {success}\n"
        f"Final Synthesized Response:\n{final_response}\n"
        f"{'='*80}\n"
    )
    
    with _log_lock:
        _write_text(footer)
        
        trace = _active_sessions[sid].get("trace")
        if trace:
            trace["final_response"] = final_response
            trace["success"] = success and trace["success"]
            trace["timestamp_end"] = datetime.now().isoformat()
            _write_json()
            
        # Clean up global active sessions registry
        if sid in _active_sessions:
            del _active_sessions[sid]
            
        # Clear thread-local context
        set_thread_session_id(None)

# --- Internal Helper Utilities ---

def _indent_text(text: str, spaces: int) -> str:
    """Helper to indent multiline text strings for readability in text logs."""
    indent = " " * spaces
    return indent + f"\n{indent}".join(text.splitlines())

def _sanitize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to clean/truncate values in State to avoid bloated traces."""
    if not isinstance(state, dict):
        return state
        
    sanitized = {}
    for k, v in state.items():
        if isinstance(v, str) and len(v) > 2000:
            sanitized[k] = v[:2000] + f"... [Truncated. Total length: {len(v)}]"
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_state(v)
        elif isinstance(v, list):
            sanitized[k] = [_sanitize_state(item) if isinstance(item, dict) else item for item in v]
        else:
            sanitized[k] = v
            
    return sanitized

def _get_active_worker_step(trace: Dict[str, Any], worker_name: str) -> Optional[Dict[str, Any]]:
    """Retrieves the currently open worker_run trace item."""
    for step in reversed(trace["steps"]):
        if step["type"] == "worker_run" and step["worker"] == worker_name and step["timestamp_end"] is None:
            return step
    return None
