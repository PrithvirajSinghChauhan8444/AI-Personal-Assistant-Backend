import os
import json
import uuid
import time
import threading
from datetime import datetime

MEMORY_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', 'Memory'))
TASKS_FILE = os.path.join(MEMORY_DIR, 'scheduled_tasks.json')

# Ensure directory exists
os.makedirs(MEMORY_DIR, exist_ok=True)
if not os.path.exists(TASKS_FILE):
    with open(TASKS_FILE, 'w') as f:
        json.dump([], f)

def load_tasks() -> list:
    """Loads tasks from scheduled_tasks.json file."""
    try:
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading tasks file: {e}")
    return []

def save_tasks(tasks: list):
    """Saves tasks list to scheduled_tasks.json file."""
    try:
        with open(TASKS_FILE, 'w') as f:
            json.dump(tasks, f, indent=4)
    except Exception as e:
        print(f"Error saving scheduled tasks: {e}")

def schedule_delayed_task(description: str, delay_seconds: int) -> str:
    """Schedules a task to run after a delay in seconds.
    
    Args:
        description (str): The task prompt/action instructions for the assistant.
        delay_seconds (int): Delay in seconds before execution.
    """
    tasks = load_tasks()
    task_id = str(uuid.uuid4())[:8]
    due_timestamp = time.time() + delay_seconds
    
    tasks.append({
        "id": task_id,
        "description": description,
        "due_at": due_timestamp,
        "status": "pending",
        "created_at": time.time()
    })
    save_tasks(tasks)
    
    due_str = datetime.fromtimestamp(due_timestamp).strftime('%I:%M:%S %p, %d %B %Y')
    return f"Successfully scheduled task '{description}' (ID: {task_id}) to run in {delay_seconds} seconds (at {due_str})."

def schedule_task_at_time(description: str, time_str: str) -> str:
    """Schedules a task to run at a specific calendar date and time.
    
    Args:
        description (str): The task prompt/action instructions for the assistant.
        time_str (str): Target time string. Can be 'HH:MM:SS' (today/tomorrow) or 'YYYY-MM-DD HH:MM:SS'.
    """
    try:
        now = datetime.now()
        
        # Try parsing full format first
        try:
            target_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Fall back to today's HH:MM:SS or HH:MM
            time_parts = [int(p) for p in time_str.split(':')]
            if len(time_parts) == 2:
                hour, minute = time_parts
                second = 0
            elif len(time_parts) == 3:
                hour, minute, second = time_parts
            else:
                raise ValueError("Invalid time format. Use 'HH:MM:SS' or 'YYYY-MM-DD HH:MM:SS'")
                
            target_dt = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
            if target_dt < now:
                # If target time has already passed today, assume tomorrow
                from datetime import timedelta
                target_dt += timedelta(days=1)
                
        due_timestamp = target_dt.timestamp()
        delay = due_timestamp - time.time()
        
        if delay <= 0:
            return "❌ Scheduling Error: The specified target time is in the past."
            
        tasks = load_tasks()
        task_id = str(uuid.uuid4())[:8]
        tasks.append({
            "id": task_id,
            "description": description,
            "due_at": due_timestamp,
            "status": "pending",
            "created_at": time.time()
        })
        save_tasks(tasks)
        
        due_str = target_dt.strftime('%I:%M:%S %p, %d %B %Y')
        return f"Successfully scheduled task '{description}' (ID: {task_id}) to run at {due_str}."
    except Exception as e:
        return f"❌ Scheduling Error parsing time string '{time_str}': {e}"

def list_scheduled_tasks() -> str:
    """Lists all pending scheduled tasks."""
    tasks = load_tasks()
    pending = [t for t in tasks if t["status"] == "pending"]
    if not pending:
        return "No pending scheduled tasks."
        
    lines = ["Pending Scheduled Tasks:"]
    for t in pending:
        due_str = datetime.fromtimestamp(t["due_at"]).strftime('%I:%M:%S %p, %d %B %Y')
        lines.append(f"- ID: {t['id']} | Task: '{t['description']}' | Due: {due_str}")
    return "\n".join(lines)

def cancel_scheduled_task(task_id: str) -> str:
    """Cancels a pending scheduled task by its ID."""
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id and t["status"] == "pending":
            t["status"] = "cancelled"
            save_tasks(tasks)
            return f"Successfully cancelled scheduled task {task_id}."
    return f"No pending task found with ID {task_id}."

# --- Active Daemon Thread Execution ---

def run_due_task(task_id: str, description: str):
    """Executes the task in a background daemon thread by invoking the StateGraph app."""
    try:
        from src.CoreFunctions.StateGraph.main_graph import app
    except ImportError as e:
        print(f"\n❌ [Scheduler Daemon] Failed to import main_graph app: {e}")
        return
        
    config = {"configurable": {"thread_id": f"scheduled_{task_id}"}}
    initial_state = {
        "primary_goal": description,
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": "",
        "chat_history": []
    }
    
    print(f"\n⏰ [Scheduler Daemon] Running scheduled task ID {task_id}: '{description}'...")
    try:
        # Run graph synchronously inside this background thread
        app.invoke(initial_state, config=config)
        print(f"\n✅ [Scheduler Daemon] Task ID {task_id} successfully completed.")
    except Exception as e:
        print(f"\n❌ [Scheduler Daemon] Task ID {task_id} failed during execution: {e}")

def polling_loop():
    """Background polling loop that checks for due tasks every second."""
    # Prevent duplicate polling loops if this file is imported multiple times
    current_thread = threading.current_thread()
    if not current_thread.name.startswith("SchedulerPolling"):
        current_thread.name = f"SchedulerPolling_{current_thread.ident}"
        
    while True:
        try:
            tasks = load_tasks()
            now = time.time()
            changed = False
            
            for t in tasks:
                if t["status"] == "pending" and now >= t["due_at"]:
                    t["status"] = "running"
                    changed = True
                    # Run task in a separate worker thread so we don't block polling
                    worker = threading.Thread(
                        target=run_due_task, 
                        args=(t["id"], t["description"]),
                        name=f"SchedulerWorker_{t['id']}",
                        daemon=True
                    )
                    worker.start()
                    
            if changed:
                save_tasks(tasks)
        except Exception as e:
            print(f"\n⚠️ [Scheduler Daemon] Error in polling loop: {e}")
            
        time.sleep(1)

# Start background thread automatically
scheduler_thread = threading.Thread(target=polling_loop, name="SchedulerPolling", daemon=True)
scheduler_thread.start()
