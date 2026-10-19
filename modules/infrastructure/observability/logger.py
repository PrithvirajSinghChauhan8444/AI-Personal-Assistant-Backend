import os
import json
import threading
from datetime import datetime
from typing import Dict, Any, Optional

_log_lock = threading.Lock()

class ModuleLogger:
    """Structured JSON & human-readable execution tracer."""
    def __init__(self, log_dir: Optional[str] = None):
        if not log_dir:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            log_dir = os.path.join(project_root, "Memory", "logs")
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

    def log_event(self, module_name: str, event_type: str, data: Dict[str, Any]):
        timestamp = datetime.now().isoformat()
        entry = {
            "timestamp": timestamp,
            "module": module_name,
            "event": event_type,
            "data": data
        }
        with _log_lock:
            log_file = os.path.join(self.log_dir, "modular_execution.jsonl")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
