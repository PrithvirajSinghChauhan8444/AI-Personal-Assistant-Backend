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
from CoreFunctions.security_utils import is_path_safe, is_extension_safe



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
        account (str): The target Google account, either 'personal', 'college', or 'both' to fetch from both accounts. Defaults to 'personal'.
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
        account (str): The target Google account, either 'personal', 'college', or 'both'. Defaults to 'personal'.
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
        account (str): The target Google account, either 'personal', 'college', or 'both'. Defaults to 'personal'.
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
        account (str): The target Google account, either 'personal', 'college', or 'both'. Defaults to 'personal'.
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

def index_directory_tool(path: str) -> str:
    """Recursively scans and indexes files inside a folder for semantic RAG search.

    Args:
        path (str): The folder path to index (must be in sandboxed directory).
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: index_directory_tool")
    print(f"   Args: path={path}")
    from CoreFunctions.file_vector_store import index_directory_recursive
    return index_directory_recursive(path)

def search_files_semantically_tool(query: str, limit: int = 5) -> str:
    """Performs semantic search queries over the contents of all indexed sandboxed files.

    Args:
        query (str): The semantic query or question to search for in files.
        limit (int, optional): Maximum number of matching chunks to return. Defaults to 5.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: search_files_semantically_tool")
    print(f"   Args: query={query}, limit={limit}")
    from CoreFunctions.file_vector_store import search_files_semantically
    return search_files_semantically(query, limit)

def rag_file_qa_tool(query: str, filepath: str) -> str:
    """Uses Retrieval-Augmented Generation to answer a question specifically about a single file.
    Highly recommended for large code scripts, JSON files, or notes.

    Args:
        query (str): The specific question about the file contents.
        filepath (str): The target file path.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: rag_file_qa_tool")
    print(f"   Args: query={query}, filepath={filepath}")
    from CoreFunctions.file_vector_store import rag_qa_file
    return rag_qa_file(query, filepath)

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


# (Registry moved to the bottom of the file to prevent NameErrors)

# ===========================
# 8. OBSIDIAN TOOLS
# ===========================

OBSIDIAN_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", "/home/prit/Documents/Obsidian Vaultt")

def create_obsidian_note(filename: str, content: str, folder: str = "") -> str:
    """Creates a new note inside the Obsidian vault with raw content.
    Supports dynamic parent folder creation automatically. You can pass nested paths in the 'filename' parameter (e.g. 'logs/daily.md') or in the 'folder' parameter (e.g. 'logs').

    Args:
        filename (str): The filename of the note (e.g. 'Project Log.md' or 'category/Profile.md').
        content (str): The markdown body content to write in the note.
        folder (str): Optional subfolder within the vault (e.g. 'logs'). Defaults to empty string.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: create_obsidian_note")
    print(f"   Args: filename={filename}, folder={folder}")
    try:
        # Ensure file has .md extension
        if not filename.endswith(".md") and not filename.endswith(".canvas"):
            filename += ".md"
            
        file_path = os.path.abspath(os.path.join(OBSIDIAN_VAULT_PATH, folder, filename))
        
        if not is_path_safe(file_path):
            return f"❌ Security Violation: Access to path '{file_path}' is denied. Out of sandbox."
            
        # Create all parent directories dynamically (handling folders inside filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully created note '{filename}' at path: {file_path}"
    except Exception as e:
        return f"Error creating obsidian note: {e}"

def append_to_obsidian_note(filename: str, content: str, folder: str = "") -> str:
    """Appends logs, summaries, or tasks to an existing Obsidian note.

    Args:
        filename (str): The filename of the note to append to.
        content (str): The markdown content to append.
        folder (str): Optional subfolder inside the vault. Defaults to empty string.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: append_to_obsidian_note")
    print(f"   Args: filename={filename}, folder={folder}")
    try:
        if not filename.endswith(".md"):
            filename += ".md"
        file_path = os.path.abspath(os.path.join(OBSIDIAN_VAULT_PATH, folder, filename))
        
        if not is_path_safe(file_path):
            return f"❌ Security Violation: Access to path '{file_path}' is denied. Out of sandbox."
            
        # Create all parent directories dynamically (handling folders inside filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        if not os.path.exists(file_path):
            return create_obsidian_note(filename, content, folder)
            
        with open(file_path, "a", encoding="utf-8") as f:
            f.write("\n" + content)
        return f"Successfully appended content to note '{filename}'"
    except Exception as e:
        return f"Error appending to obsidian note: {e}"

def search_obsidian_vault(query: str) -> str:
    """Performs a global search across all notes in the vault for a keyword or tag.

    Args:
        query (str): The keyword or tag to search for.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: search_obsidian_vault")
    print(f"   Args: query={query}")
    try:
        matches = []
        # Search all .md files recursively
        for root, _, files in os.walk(OBSIDIAN_VAULT_PATH):
            for file in files:
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            if query.lower() in content.lower():
                                rel_path = os.path.relpath(full_path, OBSIDIAN_VAULT_PATH)
                                matches.append(f"- [[{rel_path[:-3]}]]")
                    except Exception:
                        continue
        if not matches:
            return f"No notes found matching query: '{query}'"
        return "Matching notes found:\n" + "\n".join(matches[:15])
    except Exception as e:
        return f"Error searching obsidian vault: {e}"

def get_note_backlinks(note_title: str) -> str:
    """Finds all notes in the vault that link to the specified note (bidirectional backlinks).

    Args:
        note_title (str): The exact title of the note to find backlinks for (without the extension).
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_note_backlinks")
    try:
        backlinks = []
        # Search all md files recursively
        for root, _, files in os.walk(OBSIDIAN_VAULT_PATH):
            for file in files:
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            # Matches [[note_title]] or [[note_title|custom label]] or [[note_title#header]]
                            pattern = rf"\[\[{re.escape(note_title)}(\|[0-9a-zA-Z\s]+)?(#[0-9a-zA-Z\s]+)?\]\]"
                            if re.search(pattern, content):
                                rel_path = os.path.relpath(full_path, OBSIDIAN_VAULT_PATH)
                                backlinks.append(f"- [[{rel_path[:-3]}]]")
                    except Exception:
                        continue
        if not backlinks:
            return f"No backlinks found linking to: '[[{note_title}]]'"
        return f"Notes linking to [[{note_title}]]:\n" + "\n".join(backlinks)
    except Exception as e:
        return f"Error fetching backlinks: {e}"

def get_note_properties(filename: str, folder: str = "") -> str:
    """Parses and returns the YAML frontmatter properties from an Obsidian note.

    Args:
        filename (str): The filename of the note (e.g. 'My Profile.md').
        folder (str): Optional subfolder. Defaults to empty string.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_note_properties")
    try:
        if not filename.endswith(".md"):
            filename += ".md"
        file_path = os.path.join(OBSIDIAN_VAULT_PATH, folder, filename)
        if not os.path.exists(file_path):
            return f"Note '{filename}' does not exist."
            
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not match:
            return "No properties found (YAML frontmatter is empty)."
            
        import yaml
        properties = yaml.safe_load(match.group(1))
        return json.dumps(properties, indent=4)
    except Exception as e:
        return f"Error parsing properties: {e}"

def update_note_properties(filename: str, properties: dict, folder: str = "") -> str:
    """Creates or updates properties inside the note's YAML frontmatter.

    Args:
        filename (str): The filename of the note.
        properties (dict): A dictionary of properties to set or merge.
        folder (str): Optional subfolder. Defaults to empty string.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: update_note_properties")
    try:
        if not filename.endswith(".md"):
            filename += ".md"
        file_path = os.path.join(OBSIDIAN_VAULT_PATH, folder, filename)
        
        import yaml
        content = ""
        existing_props = {}
        body = ""
        
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
            if match:
                try:
                    existing_props = yaml.safe_load(match.group(1)) or {}
                except Exception:
                    pass
                body = match.group(2)
            else:
                body = content
                
        existing_props.update(properties)
        yaml_str = yaml.safe_dump(existing_props, default_flow_style=False, sort_keys=False)
        new_content = f"---\n{yaml_str}---\n{body}"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"Successfully updated properties for note '{filename}'"
    except Exception as e:
        return f"Error updating properties: {e}"

def create_or_update_obsidian_canvas(canvas_name: str, nodes: list, edges: list = None, folder: str = "") -> str:
    """Creates or updates an Obsidian Canvas (.canvas) infinite whiteboard.

    Args:
        canvas_name (str): The filename of the canvas (e.g. 'Project Mindmap.canvas').
        nodes (list): A list of dictionaries representing nodes. Each node can contain:
                      - 'id' (str, unique)
                      - 'type' (str: 'text' or 'file' or 'group')
                      - 'x' (int), 'y' (int)
                      - 'width' (int), 'height' (int)
                      - 'text' (str, if type is 'text')
                      - 'file' (str, if type is 'file', relative path in vault)
                      - 'color' (str, '1' to '6' representing Obsidian colors)
        edges (list, optional): A list of dictionaries representing edges connecting nodes. Each edge can contain:
                      - 'id' (str, unique)
                      - 'fromNode' (str), 'toNode' (str)
                      - 'fromSide' (str: 'top', 'bottom', 'left', 'right')
                      - 'toSide' (str: 'top', 'bottom', 'left', 'right')
                      - 'label' (str, optional)
        folder (str): Optional subfolder within the vault. Defaults to empty string.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: create_or_update_obsidian_canvas")
    print(f"   Args: canvas_name={canvas_name}, folder={folder}")
    try:
        if not canvas_name.endswith(".canvas"):
            canvas_name += ".canvas"
        
        file_path = os.path.abspath(os.path.join(OBSIDIAN_VAULT_PATH, folder, canvas_name))
        
        if not is_path_safe(file_path):
            return f"❌ Security Violation: Access to path '{file_path}' is denied. Out of sandbox."
            
        # Create all parent directories dynamically (handling folders inside canvas name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        canvas_data = {"nodes": [], "edges": []}
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    canvas_data = json.load(f)
            except Exception:
                pass
        
        # Merge or replace nodes
        existing_nodes = {n["id"]: n for n in canvas_data.get("nodes", [])}
        for node in nodes:
            existing_nodes[node["id"]] = node
        canvas_data["nodes"] = list(existing_nodes.values())
        
        # Merge or replace edges
        if edges is not None:
            existing_edges = {e["id"]: e for e in canvas_data.get("edges", [])}
            for edge in edges:
                existing_edges[edge["id"]] = edge
            canvas_data["edges"] = list(existing_edges.values())
            
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(canvas_data, f, indent=4)
            
        return f"Successfully updated Canvas '{canvas_name}' at path: {file_path}"
    except Exception as e:
        return f"Error managing obsidian canvas: {e}"


# ===========================
# 4C. BROWSER CONTROL (Accessibility Tree Method)
# ===========================

_playwright_ctx = None
_browser = None
_browser_context = None
_page = None

async def _get_browser_page():
    global _playwright_ctx, _browser, _browser_context, _page
    if _page is None or _page.is_closed():
        from playwright.async_api import async_playwright
        import os
        from dotenv import load_dotenv
        load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..', '.env')), override=True)
        
        if _playwright_ctx is None:
            _playwright_ctx = await async_playwright().start()
            
        browser_type_str = os.getenv("BROWSER_TYPE", "chromium").lower()
        if browser_type_str not in ["chromium", "firefox", "webkit"]:
            browser_type_str = "chromium"
            
        user_data_dir = os.getenv("BROWSER_USER_DATA_DIR", "").strip()
        if user_data_dir:
            user_data_dir = os.path.expanduser(user_data_dir)
            
        headless_mode = os.getenv("BROWSER_HEADLESS", "True").lower() == "true"
        slow_mo_ms = int(os.getenv("BROWSER_SLOW_MO", "0"))
        
        browser_launcher = getattr(_playwright_ctx, browser_type_str)
        
        if _browser_context is None:
            if user_data_dir:
                print(f"🌐 [Browser] Launching {browser_type_str} with persistent context at {user_data_dir} (headless={headless_mode}, slow_mo={slow_mo_ms}ms)...", flush=True)
                _browser_context = await browser_launcher.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=headless_mode,
                    slow_mo=slow_mo_ms
                )
            else:
                if _browser is None:
                    print(f"🌐 [Browser] Launching {browser_type_str} (headless={headless_mode}, slow_mo={slow_mo_ms}ms)...", flush=True)
                    launch_kwargs = {
                        "headless": headless_mode,
                        "slow_mo": slow_mo_ms,
                    }
                    if browser_type_str == "chromium":
                        launch_kwargs["args"] = ["--password-store=basic"]
                    _browser = await browser_launcher.launch(**launch_kwargs)
                
                _browser_context = await _browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" if browser_type_str == "chromium" else None
                )
        
        _page = await _browser_context.new_page()
    return _page

DOM_TAGGING_SCRIPT = """
() => {
    // 1. Remove previous tags if any
    const oldTags = document.querySelectorAll('[data-agent-id]');
    oldTags.forEach(el => el.removeAttribute('data-agent-id'));

    const candidates = document.querySelectorAll(
        'button, a, input, select, textarea, [role="button"], [onclick], [tabindex="0"]'
    );
    
    let idCounter = 0;
    const interactiveElements = [];

    candidates.forEach(el => {
        // Filter out elements that are not visible or off-screen
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        const isVisible = rect.width > 0 && 
                          rect.height > 0 && 
                          style.display !== 'none' && 
                          style.visibility !== 'hidden' &&
                          style.opacity !== '0';
                          
        if (isVisible) {
            const id = idCounter++;
            el.setAttribute('data-agent-id', id.toString());
            
            // Build a friendly name / description
            let text = el.innerText.trim();
            if (!text && el.placeholder) text = el.placeholder.trim();
            if (!text && el.getAttribute('aria-label')) text = el.getAttribute('aria-label').trim();
            if (!text && el.value) text = el.value.trim();
            if (!text && el.title) text = el.title.trim();
            if (!text) text = el.name || "";
            
            interactiveElements.push({
                id: id,
                tag: el.tagName.toLowerCase(),
                type: el.type || "",
                text: text,
                role: el.getAttribute('role') || ""
            });
        }
    });

    return interactiveElements;
}
"""

async def _get_elements_formatted() -> str:
    page = await _get_browser_page()
    try:
        elements = await page.evaluate(DOM_TAGGING_SCRIPT)
        if not elements:
            return "No interactive elements found on this page."
        
        lines = []
        for el in elements:
            type_str = f" (type='{el['type']}')" if el['type'] else ""
            role_str = f" [role='{el['role']}']" if el['role'] else ""
            lines.append(f"[{el['id']}] {el['tag'].upper()}: \"{el['text']}\"{type_str}{role_str}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error gathering page elements: {e}"

async def browser_navigate(url: str) -> str:
    """Navigates the browser to the specified URL and returns its interactive elements.

    Args:
        url (str): The web address to navigate to (e.g. 'https://github.com').
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_navigate")
    print(f"   Args: url={url}")
    try:
        page = await _get_browser_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)
        elements_str = await _get_elements_formatted()
        return elements_str
    except Exception as e:
        return f"Error navigating browser: {e}"

async def browser_click(element_id: int) -> str:
    """Clicks an interactive element matching a specific numerical element_id.

    Args:
        element_id (int): The unique numerical ID of the element on the page.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_click")
    print(f"   Args: element_id={element_id}")
    try:
        page = await _get_browser_page()
        selector = f'[data-agent-id="{element_id}"]'
        await page.click(selector, timeout=10000)
        try:
            await page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)
        elements_str = await _get_elements_formatted()
        return elements_str
    except Exception as e:
        return f"Error clicking element [{element_id}]: {e}"

async def browser_click_selector(selector: str) -> str:
    """Clicks an element matching a CSS or text selector. Helpful if role or ID-based matching fails.

    Args:
        selector (str): The CSS selector (e.g. 'button#submit').
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_click_selector")
    print(f"   Args: selector={selector}")
    try:
        page = await _get_browser_page()
        await page.click(selector, timeout=10000)
        try:
            await page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)
        elements_str = await _get_elements_formatted()
        return elements_str
    except Exception as e:
        return f"Error clicking selector '{selector}': {e}"

async def browser_input(element_id: int, text: str) -> str:
    """Fills a text input field matching a specific numerical element_id with text.

    Args:
        element_id (int): The unique numerical ID of the input field.
        text (str): The text string to enter.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_input")
    print(f"   Args: element_id={element_id}, text={text}")
    try:
        page = await _get_browser_page()
        selector = f'[data-agent-id="{element_id}"]'
        await page.fill(selector, text, timeout=10000)
        await page.wait_for_timeout(1000)
        elements_str = await _get_elements_formatted()
        return elements_str
    except Exception as e:
        return f"Error filling element [{element_id}]: {e}"

async def browser_input_selector(selector: str, text: str) -> str:
    """Fills an input field matching a CSS or text selector with text.

    Args:
        selector (str): The CSS or text selector of the input field.
        text (str): The text to type.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_input_selector")
    print(f"   Args: selector={selector}, text={text}")
    try:
        page = await _get_browser_page()
        await page.fill(selector, text, timeout=10000)
        await page.wait_for_timeout(1000)
        elements_str = await _get_elements_formatted()
        return elements_str
    except Exception as e:
        return f"Error filling selector '{selector}': {e}"

async def browser_go_back() -> str:
    """Navigates back to the previous page in the browser history."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_go_back")
    try:
        page = await _get_browser_page()
        await page.go_back(timeout=10000)
        try:
            await page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)
        elements_str = await _get_elements_formatted()
        return elements_str
    except Exception as e:
        return f"Error going back: {e}"


# ===========================
# GitHub Tools
# ===========================
def get_github_profile_tool(username: str = None) -> str:
    """Fetches basic profile information for a GitHub account.
    
    Args:
        username (str, optional): The target GitHub username. If not provided, it falls back to the configured username or authenticated token.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_github_profile_tool")
    try:
        from Apps.Github.github_ops import get_github_profile
        res = get_github_profile(username)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error fetching GitHub profile: {e}"

def list_github_repos_tool(username: str = None, sort: str = "updated", count: int = 5) -> str:
    """Lists repositories for a GitHub user.
    
    Args:
        username (str, optional): The target GitHub username.
        sort (str, optional): Property to sort repositories by ('created', 'updated', 'pushed', 'full_name'). Defaults to 'updated'.
        count (int, optional): The number of repositories to list. Defaults to 5.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: list_github_repos_tool")
    try:
        from Apps.Github.github_ops import list_github_repos
        res = list_github_repos(username, sort=sort, count=count)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error listing repositories: {e}"

def get_github_recent_activity_tool(username: str = None, count: int = 5) -> str:
    """Retrieves recent public activity events for a GitHub user.
    
    Args:
        username (str, optional): The target GitHub username.
        count (int, optional): The number of recent events to retrieve. Defaults to 5.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_github_recent_activity_tool")
    try:
        from Apps.Github.github_ops import get_github_recent_activity
        res = get_github_recent_activity(username, count=count)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error retrieving recent activity: {e}"

def list_github_commits_tool(repo_name: str, username: str = None, branch: str = None, count: int = 5) -> str:
    """Lists recent commits for a given GitHub repository.
    
    Args:
        repo_name (str): The name of the repository.
        username (str, optional): The owner/organization of the repository. If not provided, falls back to the configured username.
        branch (str, optional): The branch name to fetch commits from (e.g. 'main', 'development').
        count (int, optional): The number of recent commits to retrieve. Defaults to 5.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: list_github_commits_tool")
    try:
        from Apps.Github.github_ops import list_github_commits
        res = list_github_commits(repo_name, username=username, branch=branch, count=count)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error listing commits: {e}"

def list_github_branches_tool(repo_name: str, username: str = None) -> str:
    """Lists the branches of a given GitHub repository.
    
    Args:
        repo_name (str): The name of the repository.
        username (str, optional): The owner/organization of the repository. If not provided, falls back to the configured username.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: list_github_branches_tool")
    try:
        from Apps.Github.github_ops import list_github_branches
        res = list_github_branches(repo_name, username=username)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error listing branches: {e}"


# ===========================
# 5. THE REGISTRY (The Menu)
# ===========================
# The AI will output these keys to call the functions.

AVAILABLE_TOOLS = {
    # GitHub
    "get_github_profile": get_github_profile_tool,
    "list_github_repos": list_github_repos_tool,
    "get_github_recent_activity": get_github_recent_activity_tool,
    "list_github_commits": list_github_commits_tool,
    "list_github_branches": list_github_branches_tool,

    # Browser Control
    "browser_navigate": browser_navigate,
    "browser_click": browser_click,
    "browser_click_selector": browser_click_selector,
    "browser_input": browser_input,
    "browser_input_selector": browser_input_selector,
    "browser_go_back": browser_go_back,

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
    "index_directory": index_directory_tool,
    "search_files_semantically": search_files_semantically_tool,
    "rag_file_qa": rag_file_qa_tool,

    # System
    "run_cmd": run_terminal_tool,
    "run_script": run_python_tool,
    "launch_app": launch_app_tool,

    # Obsidian
    "create_obsidian_note": create_obsidian_note,
    "append_to_obsidian_note": append_to_obsidian_note,
    "search_obsidian_vault": search_obsidian_vault,
    "get_note_backlinks": get_note_backlinks,
    "get_note_properties": get_note_properties,
    "update_note_properties": update_note_properties,
    "create_or_update_obsidian_canvas": create_or_update_obsidian_canvas
}




