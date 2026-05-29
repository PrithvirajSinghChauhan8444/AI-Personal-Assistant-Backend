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

def fetch_unread_mails(limit: int = 5, account: str = "personal") -> str:
    """Fetches the latest unread emails for a specific Google account.

    Args:
        limit (int): The maximum number of emails to fetch. Defaults to 5.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_unread_mails")
    print(f"   Args: limit={limit}, account={account}")
    try:
        from Apps.Gmail.gmail_ops import search_gmail_emails
        res = search_gmail_emails("is:unread", limit, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error fetching mails: {e}"

def send_gmail(to: str, subject: str, body: str, account: str = "personal") -> str:
    """Sends an email to a specified recipient from a specific Google account.

    Args:
        to (str): The email address of the recipient.
        subject (str): The subject line of the email.
        body (str): The main content or body of the email.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: send_gmail")
    print(f"   Args: to={to}, subject={subject}, body={body}, account={account}")
    try:
        from Apps.Gmail.gmail_ops import send_gmail_email
        result = send_gmail_email(to, subject, body, account=account)
        return f"Email Status: {result}"
    except Exception as e:
        return f"Error sending email: {e}"

def search_gmail(query: str, max_results: int = 10, account: str = "personal") -> str:
    """Search for emails in the user's Gmail mailbox using query syntax.

    Args:
        query (str): The search query (e.g. 'from:example@gmail.com', 'subject:meeting', 'is:unread').
        max_results (int): The maximum number of results to return. Defaults to 10.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: search_gmail")
    print(f"   Args: query={query}, max_results={max_results}, account={account}")
    try:
        from Apps.Gmail.gmail_ops import search_gmail_emails
        res = search_gmail_emails(query, max_results, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error searching emails: {e}"

def read_gmail_msg(email_id: str, account: str = "personal") -> str:
    """Retrieve the full detailed plain-text body of a specific email.

    Args:
        email_id (str): The unique ID of the Gmail message.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: read_gmail_msg")
    print(f"   Args: email_id={email_id}, account={account}")
    try:
        from Apps.Gmail.gmail_ops import read_gmail_email
        res = read_gmail_email(email_id, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error reading email: {e}"

def trash_gmail_msg(email_id: str, account: str = "personal") -> str:
    """Move a specific email message to the Trash folder.

    Args:
        email_id (str): The unique ID of the Gmail message.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: trash_gmail_msg")
    print(f"   Args: email_id={email_id}, account={account}")
    try:
        from Apps.Gmail.gmail_ops import trash_gmail_email
        return trash_gmail_email(email_id, account=account)
    except Exception as e:
        return f"Error trashing email: {e}"

def mark_gmail_read(email_id: str, account: str = "personal") -> str:
    """Mark an email message as read by removing the UNREAD label.

    Args:
        email_id (str): The unique ID of the Gmail message.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: mark_gmail_read")
    print(f"   Args: email_id={email_id}, account={account}")
    try:
        from Apps.Gmail.gmail_ops import mark_gmail_as_read
        return mark_gmail_as_read(email_id, account=account)
    except Exception as e:
        return f"Error marking email as read: {e}"

def reply_to_gmail(email_id: str, body: str, account: str = "personal") -> str:
    """Reply to a specific email, keeping it threaded correctly.

    Args:
        email_id (str): The ID of the email to reply to.
        body (str): The content of your reply.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: reply_to_gmail")
    print(f"   Args: email_id={email_id}, body={body[:50]}..., account={account}")
    try:
        from Apps.Gmail.gmail_ops import reply_to_gmail_email
        return reply_to_gmail_email(email_id, body, account=account)
    except Exception as e:
        return f"Error replying to email: {e}"

# ===========================
# 3. PRODUCTIVITY TOOLS (Tasks & Calendar)
# ===========================

def add_google_task(title: str, account: str = "personal") -> str:
    """Adds a task to Google Tasks.

    Args:
        title (str): The title or name of the task to add.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: add_google_task")
    print(f"   Args: title={title}, account={account}")
    try:
        success = add_new_task(title, account=account)
        if success:
            return f"Task '{title}' added successfully on account '{account}'."
        return f"Failed to add task on account '{account}'."
    except Exception as e:
        return f"Error adding task: {e}"

def check_calendar_events(max_results: int = 5, account: str = "personal") -> str:
    """Checks upcoming calendar events.

    Args:
        max_results (int): The maximum number of upcoming events to check. Defaults to 5.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: check_calendar_events")
    print(f"   Args: max_results={max_results}, account={account}")
    try:
        events = list_upcoming_events(max_results, account=account)
        
        # --- FIX: Handle if 'events' is None or an Error String ---
        if not events:
            return f"No upcoming events found on account '{account}'."
        
        if isinstance(events, str):
            return f"Calendar Error: {events}"
        # -----------------------------------------------------------

        # Format list into a readable string for the AI
        event_str = f"Upcoming Events ({account} account):\n"
        for e in events:
            # Safe .get() calls
            start = e.get('start', {}).get('dateTime', 'Unknown Time')
            summary = e.get('summary', 'No Title')
            event_str += f"- {summary} at {start}\n"
        return event_str
    except Exception as e:
        return f"Error reading calendar: {e}"
    

def add_calendar_event(summary: str, start_time: str, duration: int = 1, account: str = "personal") -> str:
    """Adds an event to the calendar.

    Args:
        summary (str): The title or description of the event.
        start_time (str): The start time expected in ISO format (e.g., 'YYYY-MM-DDTHH:MM:SS').
        duration (int): The duration of the event in hours. Defaults to 1.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: add_calendar_event")
    print(f"   Args: summary={summary}, start_time={start_time}, duration={duration}, account={account}")
    try:
        result = create_new_event(summary, start_time, duration, account=account)
        if result:
            return f"Event '{summary}' created on account '{account}'. Link: {result.get('htmlLink')}"
        return f"Failed to create event on account '{account}'."
    except Exception as e:
        return f"Error creating event: {e}"

def fetch_classroom_courses(account: str = "personal") -> str:
    """Lists the Google Classroom courses that the user is enrolled in or teaching.

    Args:
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_classroom_courses")
    print(f"   Args: account={account}")
    try:
        from Apps.Classroom.classroom_ops import list_courses
        res = list_courses(account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error listing courses: {e}"

def fetch_classroom_assignments(course_id: str, account: str = "personal") -> str:
    """Lists coursework (assignments) for a specific Google Classroom course ID.

    Args:
        course_id (str): The unique course ID.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_classroom_assignments")
    print(f"   Args: course_id={course_id}, account={account}")
    try:
        from Apps.Classroom.classroom_ops import list_coursework
        res = list_coursework(course_id, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error listing coursework: {e}"

def fetch_classroom_announcements(course_id: str, account: str = "personal") -> str:
    """Lists announcements for a specific Google Classroom course ID.

    Args:
        course_id (str): The unique course ID.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_classroom_announcements")
    print(f"   Args: course_id={course_id}, account={account}")
    try:
        from Apps.Classroom.classroom_ops import list_announcements
        res = list_announcements(course_id, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error listing announcements: {e}"

def fetch_classroom_assignment_details(course_id: str, coursework_id: str, account: str = "personal") -> str:
    """Retrieves full details for a specific Google Classroom coursework (assignment) ID.

    Args:
        course_id (str): The Classroom course ID.
        coursework_id (str): The specific assignment ID.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_classroom_assignment_details")
    print(f"   Args: course_id={course_id}, coursework_id={coursework_id}, account={account}")
    try:
        from Apps.Classroom.classroom_ops import get_coursework_details
        res = get_coursework_details(course_id, coursework_id, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error fetching coursework details: {e}"

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

def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for real-time information or questions.

    Args:
        query (str): The search term or question to query.
        max_results (int, optional): The maximum number of results to fetch. Defaults to 5.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: web_search")
    print(f"   Args: query={query}")
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n")
        if not results:
            return "No search results found."
        return "\n".join(results)[:3000] # Truncate for token safety
    except Exception as e:
        return f"Error executing web search: {e}"

def run_code(code):
    code

# ===========================
# 4B. ADVANCED SYSTEM ACTIONS
# ===========================

def get_audio_volume() -> str:
    """Gets the current system audio volume percentage and mute status."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_audio_volume")
    try:
        from Apps.System.system_actions import get_volume
        return get_volume()
    except Exception as e:
        return f"Error: {e}"

def set_audio_volume(level: int) -> str:
    """Sets the system audio volume to a specific percentage (0-100).
    
    Args:
        level (int): The percentage to set the volume to.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: set_audio_volume")
    try:
        from Apps.System.system_actions import set_volume
        return set_volume(level)
    except Exception as e:
        return f"Error: {e}"

def mute_audio_toggle() -> str:
    """Toggles system audio mute/unmute status."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: mute_audio_toggle")
    try:
        from Apps.System.system_actions import toggle_mute
        return toggle_mute()
    except Exception as e:
        return f"Error: {e}"

def get_screen_brightness() -> str:
    """Gets the current screen brightness percentage."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_screen_brightness")
    try:
        from Apps.System.system_actions import get_brightness
        return get_brightness()
    except Exception as e:
        return f"Error: {e}"

def set_screen_brightness(level: int) -> str:
    """Sets the screen brightness to a specific percentage (1-100).
    
    Args:
        level (int): The brightness percentage to set.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: set_screen_brightness")
    try:
        from Apps.System.system_actions import set_brightness
        return set_brightness(level)
    except Exception as e:
        return f"Error: {e}"

def control_media_player(action: str) -> str:
    """Controls background music/video media playback (play-pause, next, previous).
    
    Args:
        action (str): The media action to perform, either 'play-pause', 'next', or 'previous'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: control_media_player")
    try:
        from Apps.System.system_actions import media_control
        return media_control(action)
    except Exception as e:
        return f"Error: {e}"

def list_running_processes_tool(limit: int = 15) -> str:
    """Lists the top running desktop processes sorted by memory usage."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: list_running_processes_tool")
    try:
        from Apps.System.system_actions import list_processes
        return list_processes(limit)
    except Exception as e:
        return f"Error: {e}"

def terminate_process_tool(name_or_pid: str) -> str:
    """Terminates/kills a running process by its name or PID. PROTECTED.
    
    Args:
        name_or_pid (str): The process PID number or process name to terminate.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: terminate_process_tool")
    if verify_password():
        try:
            from Apps.System.system_actions import kill_process
            return kill_process(name_or_pid)
        except Exception as e:
            return f"Error: {e}"
    return "❌ Action Cancelled: Incorrect Password."

def lock_desktop_screen() -> str:
    """Locks the current Linux user session."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: lock_desktop_screen")
    try:
        from Apps.System.system_actions import lock_screen
        return lock_screen()
    except Exception as e:
        return f"Error: {e}"

def suspend_desktop_system() -> str:
    """Suspends the local system to RAM (sleep mode). PROTECTED."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: suspend_desktop_system")
    if verify_password():
        try:
            from Apps.System.system_actions import suspend_system
            return suspend_system()
        except Exception as e:
            return f"Error: {e}"
    return "❌ Action Cancelled: Incorrect Password."

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
    
    import sys
    import builtins
    vis = getattr(builtins, "active_cli_visualizer", None)

    if vis and vis.active:
        vis.is_paused = True
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    if verify_password():
        try:
            res = _run_term(command)
            return res
        finally:
            if vis and vis.active:
                vis.is_paused = False
    
    if vis and vis.active:
        vis.is_paused = False
    return "❌ Action Cancelled: Incorrect Password."

def run_python_tool(path: str) -> str:
    """Runs a python script at the specified path. PROTECTED.

    Args:
        path (str): The path to the Python file (.py) to execute.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: run_python_tool")
    print(f"   Args: path={path}")

    import sys
    import builtins
    vis = getattr(builtins, "active_cli_visualizer", None)

    if vis and vis.active:
        vis.is_paused = True
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    if verify_password():
        try:
            res = _run_py(path)
            return res
        finally:
            if vis and vis.active:
                vis.is_paused = False
                
    if vis and vis.active:
        vis.is_paused = False
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
    "search_gmail": search_gmail,
    "read_gmail_msg": read_gmail_msg,
    "trash_gmail_msg": trash_gmail_msg,
    "mark_gmail_read": mark_gmail_read,
    "reply_to_gmail": reply_to_gmail,
    
    # Productivity
    "add_task": add_google_task,
    "check_events": check_calendar_events,
    "add_event": add_calendar_event,
    "list_classroom_courses": fetch_classroom_courses,
    "list_classroom_assignments": fetch_classroom_assignments,
    "list_classroom_announcements": fetch_classroom_announcements,
    "get_classroom_assignment_details": fetch_classroom_assignment_details,
    
    # System / Env
    "system_health": get_system_health,
    "get_weather": get_weather,
    "get_time": get_time,
    "web_search": web_search,
    "get_volume": get_audio_volume,
    "set_volume": set_audio_volume,
    "mute_audio": mute_audio_toggle,
    "get_brightness": get_screen_brightness,
    "set_brightness": set_screen_brightness,
    "control_media": control_media_player,
    "list_processes": list_running_processes_tool,
    "kill_process": terminate_process_tool,
    "lock_screen": lock_desktop_screen,
    "suspend_system": suspend_desktop_system,

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




