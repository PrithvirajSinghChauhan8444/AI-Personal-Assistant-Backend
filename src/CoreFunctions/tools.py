import json
import os
try:
    import requests
except ImportError:
    requests = None
from datetime import datetime
import inspect


# --- IMPORT YOUR EXISTING MODULES ---
# We wrap these so the Agent can call them easily
try:
    from Apps.Gmail.gmail_handler import handle_gmail_command
    from Apps.Gmail.gmail_sender import send_email
    from Apps.Google.tasks import add_new_task
    from Apps.Calendar.read_event import list_upcoming_events
    from Apps.Calendar.create_event import create_new_event
    from Apps.System.system_monitor import get_system_stats
    # New Imports
    from Apps.FileOperations.file_manager import write_file as _write_file, read_file, list_files, create_directory as _create_dir, save_python_code as _save_code
    from Apps.SystemControl.execution import run_terminal_command as _run_term, run_python_script as _run_py, launch_app as _launch
except ImportError as e:
    print(f"⚠️ Warning: Some modules could not be imported. {e}")
from CoreFunctions.memory import store_memory, fetch_memory
from CoreFunctions.vector_memory import store_vector, search_vector
from CoreFunctions.auth_utils import verify_password


# --- FILE PATHS FOR MEMORY ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USER_INFO_PATH = os.path.join(BASE_DIR, "Memory", "user_info.json")

# Ensure memory directory exists
os.makedirs(os.path.join(BASE_DIR, "Memory"), exist_ok=True)
if not os.path.exists(USER_INFO_PATH):
    with open(USER_INFO_PATH, "w") as f:
        json.dump({"name": "User", "preferences": []}, f)

# ===========================
# 1. MEMORY TOOLS
# ===========================

def save_memory(key, value):
    """Saves a piece of information about the user."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: save_memory")
    print(f"   Args: key={key}, value={value}")
    try:
        with open(USER_INFO_PATH, "r") as f:
            data = json.load(f)
        data[key] = value
        with open(USER_INFO_PATH, "w") as f:
            json.dump(data, f, indent=4)
        return f"Memory Saved: {key} = {value}"
    except Exception as e:
        return f"Error saving memory: {e}"

def read_memory(key):
    """Retrieves information about the user."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: read_memory")
    print(f"   Args: key={key}")
    try:
        with open(USER_INFO_PATH, "r") as f:
            data = json.load(f)
        return data.get(key, "Information not found.")
    except Exception as e:
        return f"Error reading memory: {e}"



def remember(key: str, value: str, category: str = "past") -> str:
    """Store important information for future use.

    Args:
        key (str): The unique identifier or topic name for the memory (e.g., 'user_name').
        value (str): The actual details or context to remember (e.g., 'John').
        category (str): The grouping category for the memory. Defaults to 'past'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: remember")
    print(f"   Args: key={key}, value={value}, category={category}")
    store_memory(category, key, value)
    store_vector(value)
    return f"Saved memory: {key}"


def recall(key: str) -> str:
    """Recall memory by key using smart lookup.

    Args:
        key (str): The unique identifier or topic name of the memory to fetch.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: recall")
    print(f"   Args: key={key}")
    value = fetch_memory(None, key)
    return value if value else f"No memory found for '{key}'."




# ===========================
# 2. COMMUNICATION TOOLS (Gmail)
# ===========================

def fetch_unread_mails(limit: int = 5) -> str:
    """Fetches the latest unread emails.

    Args:
        limit (int): The maximum number of emails to fetch. Defaults to 5.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_unread_mails")
    print(f"   Args: limit={limit}")
    try:
        # Reusing your existing logic. 
        # Note: handle_gmail_command usually returns a dict/list
        mails = handle_gmail_command("check unread gmail")
        return str(mails)[:2000] # Truncate to avoid overflowing LLM context
    except Exception as e:
        return f"Error fetching mails: {e}"

def send_gmail(to: str, subject: str, body: str) -> str:
    """Sends an email to a specified recipient.

    Args:
        to (str): The email address of the recipient.
        subject (str): The subject line of the email.
        body (str): The main content or body of the email.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: send_gmail")
    print(f"   Args: to={to}, subject={subject}, body={body}")
    try:
        result = send_email(to, subject, body)
        return f"Email Status: {result}"
    except Exception as e:
        return f"Error sending email: {e}"

# ===========================
# 3. PRODUCTIVITY TOOLS (Tasks & Calendar)
# ===========================

def add_google_task(title: str) -> str:
    """Adds a task to Google Tasks.

    Args:
        title (str): The title or name of the task to add.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: add_google_task")
    print(f"   Args: title={title}")
    try:
        success = add_new_task(title)
        if success:
            return f"Task '{title}' added successfully."
        return "Failed to add task."
    except Exception as e:
        return f"Error adding task: {e}"

def check_calendar_events(max_results: int = 5) -> str:
    """Checks upcoming calendar events.

    Args:
        max_results (int): The maximum number of upcoming events to check. Defaults to 5.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: check_calendar_events")
    print(f"   Args: max_results={max_results}")
    try:
        events = list_upcoming_events(max_results)
        
        # --- FIX: Handle if 'events' is None or an Error String ---
        if not events:
            return "No upcoming events found."
        
        if isinstance(events, str):
            return f"Calendar Error: {events}"
        # -----------------------------------------------------------

        # Format list into a readable string for the AI
        event_str = "Upcoming Events:\n"
        for e in events:
            # Safe .get() calls
            start = e.get('start', {}).get('dateTime', 'Unknown Time')
            summary = e.get('summary', 'No Title')
            event_str += f"- {summary} at {start}\n"
        return event_str
    except Exception as e:
        return f"Error reading calendar: {e}"
    



    
def add_calendar_event(summary: str, start_time: str, duration: int = 1) -> str:
    """Adds an event to the calendar.

    Args:
        summary (str): The title or description of the event.
        start_time (str): The start time expected in ISO format (e.g., 'YYYY-MM-DDTHH:MM:SS').
        duration (int): The duration of the event in hours. Defaults to 1.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: add_calendar_event")
    print(f"   Args: summary={summary}, start_time={start_time}, duration={duration}")
    try:
        result = create_new_event(summary, start_time, duration)
        if result:
            return f"Event '{summary}' created. Link: {result.get('htmlLink')}"
        return "Failed to create event."
    except Exception as e:
        return f"Error creating event: {e}"

# ===========================
# 4. SYSTEM & ENVIRONMENT
# ===========================

def get_system_health() -> str:
    """Returns CPU, RAM, and Battery stats.

    Returns:
        str: A JSON formatted string containing system health metrics.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_system_health")
    try:
        stats = get_system_stats()
        return json.dumps(stats)
    except Exception as e:
        return f"Error reading system stats: {e}"

def get_weather(location: str = "Agra") -> str:
    """Fetches current weather using wttr.in (No API key needed).

    Args:
        location (str): The name of the city to get the weather for. Defaults to "Agra".
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_weather")
    print(f"   Args: location={location}")
    try:
        # wttr.in returns simple text or JSON. format=j1 gives JSON.
        url = f"https://wttr.in/{location}?format=%C+%t"
        response = requests.get(url)
        return f"Current weather in {location}: {response.text.strip()}"
    except Exception as e:
        return f"Error fetching weather: {e}"

def get_time() -> str:
    """Returns the current system time.

    Returns:
        str: The formatted current system time string.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_time")
    return datetime.now().strftime("%I:%M %p, %A %d %B %Y")

def run_code(code):
    code

# ===========================
# 6. FILE OPERATIONS (Protected)
# ===========================

def create_file_tool(path: str, content: str) -> str:
    """Creates a file with content. PROTECTED.

    Args:
        path (str): The absolute or relative file path to write to.
        content (str): The string content to write inside the file.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: create_file_tool")
    print(f"   Args: path={path}, content={content[:50]}...")
    if verify_password():
        return _write_file(path, content)
    return "❌ Action Cancelled: Incorrect Password."

def read_file_tool(path: str) -> str:
    """Reads and returns the contents of a file.

    Args:
        path (str): The file path to read from.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: read_file_tool")
    print(f"   Args: path={path}")
    return read_file(path)

def list_files_tool(path: str) -> str:
    """Lists files and directories inside a path.

    Args:
        path (str): The directory path to list.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: list_files_tool")
    print(f"   Args: path={path}")
    return list_files(path)

def create_dir_tool(path: str) -> str:
    """Creates a new directory. PROTECTED.

    Args:
        path (str): The path of the directory to create.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: create_dir_tool")
    print(f"   Args: path={path}")
    if verify_password():
        return _create_dir(path)
    return "❌ Action Cancelled: Incorrect Password."

def save_code_tool(content: str, suggested_name: str = None) -> str:
    """Saves python code to a script. PROTECTED.

    Args:
        content (str): The python code script contents.
        suggested_name (str, optional): The name of the file to save as. Defaults to None.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: save_code_tool")
    print(f"   Args: content={content[:50]}..., suggested_name={suggested_name}")
    if verify_password():
        return _save_code(content, suggested_name)
    return "❌ Action Cancelled: Incorrect Password."

# ===========================
# 7. SYSTEM CONTROL (Protected)
# ===========================

def run_terminal_tool(command: str) -> str:
    """Runs a bash terminal command. PROTECTED.

    Args:
        command (str): The exact shell command string to execute.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: run_terminal_tool")
    print(f"   Args: command={command}")
    if verify_password():
        return _run_term(command)
    return "❌ Action Cancelled: Incorrect Password."

def run_python_tool(path: str) -> str:
    """Runs a python script at the specified path. PROTECTED.

    Args:
        path (str): The path to the Python file (.py) to execute.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: run_python_tool")
    print(f"   Args: path={path}")
    if verify_password():
        return _run_py(path)
    return "❌ Action Cancelled: Incorrect Password."

def launch_app_tool(app_name: str, arguments: str = None) -> str:
    """Launches an installed application. PROTECTED.

    Args:
        app_name (str): The name or path of the application.
        arguments (str, optional): Arguments to pass to the application. Defaults to None.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: launch_app_tool")
    print(f"   Args: app_name={app_name}, arguments={arguments}")
    if verify_password():
        
        return _launch(app_name, arguments)
    return "❌ Action Cancelled: Incorrect Password."


# ===========================
# 5. THE REGISTRY (The Menu)
# ===========================
# The AI will output these keys to call the functions.

AVAILABLE_TOOLS = {
    # Memory
    "recall":recall,
    "remember": remember,

    
    # Communication
    "fetch_mails": fetch_unread_mails,
    "send_mail": send_gmail,
    
    # Productivity
    "add_task": add_google_task,
    "check_events": check_calendar_events,
    "add_event": add_calendar_event,
    
    # System / Env
    "system_health": get_system_health,
    "get_weather": get_weather,
    "get_time": get_time,

    # File Ops
    "write_file": create_file_tool,
    "read_file": read_file_tool,
    "list_files": list_files_tool,
    "create_directory": create_dir_tool,
    "save_code": save_code_tool,

    # System
    "run_cmd": run_terminal_tool,
    "run_script": run_python_tool,
    "launch_app": launch_app_tool
}




