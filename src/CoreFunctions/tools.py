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
    from Apps.WhatsApp.sending_message import send_message as _send_wa
    from Apps.WhatsApp.session import get_status as _wa_status, get_qr_code as _wa_qr, start_session as _wa_start
    from Apps.WhatsApp.contacts import get_contact_by_name as _find_contact
    from Apps.WhatsApp.reading_messages import read_messages as _read_messages
    from Apps.WhatsApp.manage import start_waha, stop_waha
except ImportError as e:
    print(f"⚠️ Warning: Some modules could not be imported. {e}")
from CoreFunctions.memory import store_memory, fetch_memory
try:
    from CoreFunctions.vector_memory import store_vector, search_vector
except ImportError:
    def store_vector(*args, **kwargs): pass
    def search_vector(*args, **kwargs): return []
from CoreFunctions.auth_utils import verify_password


# --- FILE PATHS FOR MEMORY ---
USER_INFO_PATH = "Memory/user_info.json"

# Ensure memory directory exists
os.makedirs("Memory", exist_ok=True)
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



def remember(key, value, category="past"):
    """Store important information for future use."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: remember")
    print(f"   Args: key={key}, value={value}, category={category}")
    store_memory(category, key, value)
    store_vector(value)
    return f"Saved memory: {key}"


def recall(key):
    """
    Recall memory by key using smart lookup.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: recall")
    print(f"   Args: key={key}")
    value = fetch_memory(None, key)
    return value if value else f"No memory found for '{key}'."




# ===========================
# 2. COMMUNICATION TOOLS (Gmail & WhatsApp)
# ===========================

def send_whatsapp_msg(to, message=None):
    """
    Sends a WhatsApp message via WAHA.
    Args:
      to: COMPULSORY. The specific target Phone number or ID (e.g. '919876543210@c.us') obtained from find_contact. Do NOT put the message text here.
      message: COMPULSORY. The text content to send.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: send_whatsapp_msg")
    print(f"   Args: to={to}, message={message}")
    if not message:
         return "❌ Error: 'message' argument is required. Please specify what to send."
    return _send_wa(to, message)

def check_whatsapp_status():
    """Checks WhatsApp connection status."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: check_whatsapp_status")
    return _wa_status()

def get_whatsapp_qr():
    """Gets WhatsApp QR code for login."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_whatsapp_qr")
    return _wa_qr()

def start_whatsapp_session(session_name="default"):
    """Starts a WhatsApp session."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: start_whatsapp_session")
    print(f"   Args: session_name={session_name}")
    return _wa_start(session_name)

def manage_whatsapp_server(action="start"):
    """Starts or stops the WAHA Docker server. Action: 'start' or 'stop'."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: manage_whatsapp_server")
    print(f"   Args: action={action}")
    if verify_password():
        if action.lower() == "start":
            return start_waha()
        elif action.lower() == "stop":
            return stop_waha()
        return "Invalid action. Use 'start' or 'stop'."
    return "❌ Action Cancelled: Incorrect Password."

def find_whatsapp_contact(name):
    """
    Searches for a WhatsApp contact by name.
    Returns Name and ID (Phone Number).
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: find_whatsapp_contact")
    print(f"   Args: name={name}")
    return _find_contact(name)

def read_whatsapp_messages(chat_id_or_name, limit=10):
    """
    Reads recent messages from a WhatsApp chat.
    Args:
      chat_id_or_name: Name (e.g., 'Praveen') or ID to read from.
      limit: Number of messages to retrieve (default 10).
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: read_whatsapp_messages")
    print(f"   Args: chat_id_or_name={chat_id_or_name}, limit={limit}")
    return _read_messages(chat_id_or_name, limit)

def fetch_unread_mails(limit=5):
    """Fetches the latest unread emails."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_unread_mails")
    print(f"   Args: limit={limit}")
    try:
        # Reusing your existing logic. 
        # Note: handle_gmail_command usually returns a dict/list
        mails = handle_gmail_command("check unread gmail")
        return str(mails)[:2000] # Truncate to avoid overflowing LLM context
    except Exception as e:
        return f"Error fetching mails: {e}"

def send_gmail(to, subject, body):
    """Sends an email."""
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

def add_google_task(title):
    """Adds a task to Google Tasks."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: add_google_task")
    print(f"   Args: title={title}")
    try:
        success = add_new_task(title)
        if success:
            return f"Task '{title}' added successfully."
        return "Failed to add task."
    except Exception as e:
        return f"Error adding task: {e}"

def check_calendar_events(max_results=5):
    """Checks upcoming calendar events."""
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
    



    
def add_calendar_event(summary, start_time, duration=1):
    """
    Adds an event to the calendar.
    start_time format expected: 'YYYY-MM-DDTHH:MM:SS' (ISO format)
    duration in hours.
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

def get_system_health():
    """Returns CPU, RAM, and Battery stats."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_system_health")
    try:
        stats = get_system_stats()
        return json.dumps(stats)
    except Exception as e:
        return f"Error reading system stats: {e}"

def get_weather(location="Agra"):
    """
    Fetches current weather using wttr.in (No API key needed).
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

def get_time():
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_time")
    return datetime.now().strftime("%I:%M %p, %A %d %B %Y")

def run_code(code):
    code

# ===========================
# 6. FILE OPERATIONS (Protected)
# ===========================

def create_file_tool(path, content):
    """Creates a file with content. PROTECTED."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: create_file_tool")
    print(f"   Args: path={path}, content={content[:50]}...")
    if verify_password():
        return _write_file(path, content)
    return "❌ Action Cancelled: Incorrect Password."

def read_file_tool(path):
    """Reads a file."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: read_file_tool")
    print(f"   Args: path={path}")
    return read_file(path)

def list_files_tool(path):
    """Lists files in a directory."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: list_files_tool")
    print(f"   Args: path={path}")
    return list_files(path)

def create_dir_tool(path):
    """Creates a directory. PROTECTED."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: create_dir_tool")
    print(f"   Args: path={path}")
    if verify_password():
        return _create_dir(path)
    return "❌ Action Cancelled: Incorrect Password."

def save_code_tool(content, suggested_name=None):
    """Saves python code. PROTECTED."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: save_code_tool")
    print(f"   Args: content={content[:50]}..., suggested_name={suggested_name}")
    if verify_password():
        return _save_code(content, suggested_name)
    return "❌ Action Cancelled: Incorrect Password."

# ===========================
# 7. SYSTEM CONTROL (Protected)
# ===========================

def run_terminal_tool(command):
    """Runs a terminal command. PROTECTED."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: run_terminal_tool")
    print(f"   Args: command={command}")
    if verify_password():
        return _run_term(command)
    return "❌ Action Cancelled: Incorrect Password."

def run_python_tool(path):
    """Runs a python script. PROTECTED."""
    print(f"\n[DEBUG] 🛠️ Calling Tool: run_python_tool")
    print(f"   Args: path={path}")
    if verify_password():
        return _run_py(path)
    return "❌ Action Cancelled: Incorrect Password."

def launch_app_tool(app_name, arguments=None):
    """Launches an app. PROTECTED."""
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
    "send_whatsapp": send_whatsapp_msg,
    "whatsapp_status": check_whatsapp_status,
    "whatsapp_qr": get_whatsapp_qr,
    "whatsapp_start": start_whatsapp_session,
    "whatsapp_server": manage_whatsapp_server,
    "find_contact": find_whatsapp_contact,
    "read_whatsapp_messages": read_whatsapp_messages,
    
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




