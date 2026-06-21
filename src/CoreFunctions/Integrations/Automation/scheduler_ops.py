import os
import json
import uuid
import time
import sys
import threading
import subprocess
from typing import Literal
from datetime import datetime

MEMORY_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', 'Memory'))
TASKS_FILE = os.path.join(MEMORY_DIR, 'scheduled_tasks.json')

# Lock for thread-safe tasks file access
_tasks_lock = threading.Lock()

# Ensure directory exists
os.makedirs(MEMORY_DIR, exist_ok=True)
if not os.path.exists(TASKS_FILE):
    with _tasks_lock:
        with open(TASKS_FILE, 'w') as f:
            json.dump([], f)

def load_tasks() -> list:
    """Loads tasks from scheduled_tasks.json file in a thread-safe manner."""
    with _tasks_lock:
        try:
            if os.path.exists(TASKS_FILE):
                with open(TASKS_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading tasks file: {e}")
        return []

def save_tasks(tasks: list):
    """Saves tasks list to scheduled_tasks.json file in a thread-safe manner."""
    with _tasks_lock:
        try:
            with open(TASKS_FILE, 'w') as f:
                json.dump(tasks, f, indent=4)
        except Exception as e:
            print(f"Error saving scheduled tasks: {e}")

def calculate_next_run(recurrence: str, current_due_at: float) -> float:
    """Calculates the next execution timestamp based on recurrence type."""
    now = time.time()
    due = current_due_at
    
    # Avoid infinite loop if due is far in the past or invalid
    if due <= 0:
        due = now

    while due <= now:
        if recurrence == "minutely":
            due += 60
        elif recurrence == "hourly":
            due += 3600
        elif recurrence == "daily":
            due += 24 * 3600
        elif recurrence == "weekly":
            due += 7 * 24 * 3600
        else:
            break
    return due

def schedule_delayed_task(description: str, delay_seconds: int, task_type: str = "agent_task", recurrence: str = None) -> str:
    """Schedules a task to run after a delay in seconds.
    
    Args:
        description (str): The task prompt/action instructions for the assistant.
        delay_seconds (int): Delay in seconds before execution.
        task_type (str): Type of task: 'reminder' or 'agent_task'. Defaults to 'agent_task'.
        recurrence (str): Recurrence interval: 'minutely', 'hourly', 'daily', 'weekly' or None. Defaults to None.
    """
    tasks = load_tasks()
    task_id = str(uuid.uuid4())[:8]
    due_timestamp = time.time() + delay_seconds
    
    tasks.append({
        "id": task_id,
        "description": description,
        "due_at": due_timestamp,
        "status": "pending",
        "type": task_type,
        "recurrence": recurrence,
        "created_at": time.time()
    })
    save_tasks(tasks)
    
    due_str = datetime.fromtimestamp(due_timestamp).strftime('%I:%M:%S %p, %d %B %Y')
    rec_str = f" (recurring: {recurrence})" if recurrence else ""
    return f"Successfully scheduled {task_type} '{description}' (ID: {task_id}) to run in {delay_seconds} seconds (at {due_str}){rec_str}."

def schedule_task_at_time(description: str, time_str: str, task_type: str = "agent_task", recurrence: str = None) -> str:
    """Schedules a task to run at a specific calendar date and time.
    
    Args:
        description (str): The task prompt/action instructions for the assistant.
        time_str (str): Target time string. Can be 'HH:MM:SS' (today/tomorrow) or 'YYYY-MM-DD HH:MM:SS'.
        task_type (str): Type of task: 'reminder' or 'agent_task'. Defaults to 'agent_task'.
        recurrence (str): Recurrence interval: 'minutely', 'hourly', 'daily', 'weekly' or None. Defaults to None.
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
        
        if delay <= 0 and not recurrence:
            return "❌ Scheduling Error: The specified target time is in the past."
            
        tasks = load_tasks()
        task_id = str(uuid.uuid4())[:8]
        tasks.append({
            "id": task_id,
            "description": description,
            "due_at": due_timestamp,
            "status": "pending",
            "type": task_type,
            "recurrence": recurrence,
            "created_at": time.time()
        })
        save_tasks(tasks)
        
        due_str = target_dt.strftime('%I:%M:%S %p, %d %B %Y')
        rec_str = f" (recurring: {recurrence})" if recurrence else ""
        return f"Successfully scheduled {task_type} '{description}' (ID: {task_id}) to run at {due_str}{rec_str}."
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
        task_type = t.get("type", "agent_task")
        recurrence = t.get("recurrence")
        rec_info = f" | Recur: {recurrence}" if recurrence else ""
        lines.append(f"- ID: {t['id']} | [{task_type.upper()}] '{t['description']}' | Due: {due_str}{rec_info}")
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

def play_beep():
    """Triggers an audible terminal bell/beep sound."""
    sys.stdout.write("\a")
    sys.stdout.flush()

def trigger_desktop_notification(title: str, message: str):
    """Triggers a desktop notification using notify-send on Linux if available."""
    try:
        subprocess.run(["notify-send", "-t", "5000", title, message], check=False)
    except Exception:
        # notify-send not available or failed
        pass

def run_due_task(task_id: str, description: str, recurrence: str = None):
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
        
        # Play audible beep on task completion
        play_beep()
        
        # Reschedule if recurring
        if recurrence:
            tasks = load_tasks()
            for t in tasks:
                if t["id"] == task_id:
                    t["due_at"] = calculate_next_run(recurrence, t["due_at"])
                    t["status"] = "pending"
                    break
            save_tasks(tasks)
        else:
            tasks = load_tasks()
            for t in tasks:
                if t["id"] == task_id:
                    t["status"] = "completed"
                    break
            save_tasks(tasks)
            
    except Exception as e:
        print(f"\n❌ [Scheduler Daemon] Task ID {task_id} failed during execution: {e}")
        tasks = load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                t["status"] = "failed"
                break
        save_tasks(tasks)

def polling_loop():
    """Background polling loop that checks for due tasks every second."""
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
                    task_type = t.get("type", "agent_task")
                    recurrence = t.get("recurrence")
                    
                    if task_type == "reminder":
                        # Play audible beep on reminder trigger
                        play_beep()
                        
                        # Trigger desktop notification
                        trigger_desktop_notification("Hermes Reminder", t["description"])
                        
                        # Print styled notification directly to CLI
                        print(f"\n\n🔔 \033[1;33m[REMINDER DUE]\033[0m {t['description']}\n")
                        
                        if recurrence:
                            t["due_at"] = calculate_next_run(recurrence, t["due_at"])
                            t["status"] = "pending"
                        else:
                            t["status"] = "completed"
                        changed = True
                    else:
                        t["status"] = "running"
                        changed = True
                        # Run task in a separate worker thread so we don't block polling
                        worker = threading.Thread(
                            target=run_due_task, 
                            args=(t["id"], t["description"], recurrence),
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
