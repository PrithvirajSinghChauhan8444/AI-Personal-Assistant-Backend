import os
import json
import base64
import hashlib
import threading
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import sys
if not hasattr(sys, "_stdout_lock"):
    sys._stdout_lock = threading.RLock()
_stdin_lock = sys._stdout_lock

class LockedWriter:
    def __init__(self, original, lock):
        self._original = original
        self._lock = lock

    def write(self, data):
        with self._lock:
            return self._original.write(data)

    def flush(self):
        with self._lock:
            return self._original.flush()

    def __getattr__(self, name):
        return getattr(self._original, name)

if not getattr(sys.stdout, "_is_locked_writer", False):
    sys.stdout = LockedWriter(sys.stdout, sys._stdout_lock)
    sys.stdout._is_locked_writer = True
    
if not getattr(sys.stderr, "_is_locked_writer", False):
    sys.stderr = LockedWriter(sys.stderr, sys._stdout_lock)
    sys.stderr._is_locked_writer = True

# The permissions your app needs
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.me',
    'https://www.googleapis.com/auth/classroom.announcements.readonly',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/youtube.readonly'
]

def get_config_dir():
    """
    Finds the config folder which is a sibling of src.
    Structure:
      ROOT/
       ├── config/
       └── src/
            └── CoreFunctions/
                 └── auth_utils.py (THIS FILE)
    """
    # 1. Get the directory containing this script (src/CoreFunctions/Infrastructure)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Go up one level to 'src/CoreFunctions'
    core_functions_dir = os.path.dirname(current_dir)
    
    # 3. Go up one level to 'src'
    src_dir = os.path.dirname(core_functions_dir)
    
    # 4. Go up one level to 'ROOT'
    root_dir = os.path.dirname(src_dir)
    
    # 5. Go into 'config'
    config_dir = os.path.join(root_dir, 'config')
    
    return config_dir

def get_encryption_key():
    """
    Retrieves or derives a 32-byte url-safe base64-encoded key for Fernet.
    Checks TOKEN_ENCRYPTION_KEY env var, then falls back to deriving from SYSTEM_PASSWORD/AGENT_PASSWORD.
    """
    key_str = os.getenv("TOKEN_ENCRYPTION_KEY")
    if not key_str:
        # Fallback to deriving from password (or a default if neither password nor key is configured)
        sys_pw = os.getenv("SYSTEM_PASSWORD") or os.getenv("AGENT_PASSWORD") or "default_secret_fallback_password"
        key_bytes = hashlib.sha256(sys_pw.encode('utf-8')).digest()
        key_str = base64.urlsafe_b64encode(key_bytes).decode('utf-8')
    else:
        # Generate a deterministic 32-byte key from the user-provided string
        key_bytes = hashlib.sha256(key_str.encode('utf-8')).digest()
        key_str = base64.urlsafe_b64encode(key_bytes).decode('utf-8')
    return key_str.encode('utf-8')

def load_encrypted_json(filepath):
    """
    Loads and decrypts a JSON file. Automatically handles unencrypted/plain JSON
    (e.g., legacy token files) by loading and writing it back encrypted.
    """
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, 'rb') as f:
            content = f.read().strip()
        
        if not content:
            return None
            
        # Handle backward compatibility: Check if it's plaintext JSON
        if content.startswith(b'{'):
            try:
                data = json.loads(content.decode('utf-8'))
                # Re-save as encrypted immediately
                save_encrypted_json(filepath, data)
                return data
            except Exception as e:
                print(f"❌ Failed to parse plain JSON in legacy file: {e}")
                return None
        
        # Decrypt using Fernet
        key = get_encryption_key()
        fernet = Fernet(key)
        decrypted = fernet.decrypt(content)
        return json.loads(decrypted.decode('utf-8'))
    except Exception as e:
        print(f"❌ Decryption failed for {filepath}: {e}")
        return None

def save_encrypted_json(filepath, data):
    """
    Encrypts and saves a dictionary as a file, setting restricted permissions (owner read/write only).
    """
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        plain_text = json.dumps(data).encode('utf-8')
        encrypted = fernet.encrypt(plain_text)
        with open(filepath, 'wb') as f:
            f.write(encrypted)
        try:
            os.chmod(filepath, 0o600)
        except Exception:
            pass
    except Exception as e:
        print(f"❌ Failed to save encrypted JSON to {filepath}: {e}")
        raise e

def get_valid_credentials(account: str = "personal"):
    """
    The Master Auth Function.
    1. Checks if token exists and is valid.
    2. Auto-refreshes if expired.
    3. Auto-launches Browser Login if token is missing/dead.
    """
    config_dir = get_config_dir()
    
    # Ensure config dir exists (sanity check)
    if not os.path.exists(config_dir):
        print(f"❌ Error: Config folder not found at: {config_dir}")
        return None

    # Load from account specific token file (e.g. token_personal.json or token_college.json)
    token_path = os.path.join(config_dir, f'token_{account}.json')
    # Backward compatibility fallback
    if account == "personal" and not os.path.exists(token_path) and os.path.exists(os.path.join(config_dir, 'token.json')):
        token_path = os.path.join(config_dir, 'token.json')

    credentials_path = os.path.join(config_dir, 'credentials.json')

    creds = None

    # --- STEP 1: LOAD EXISTING TOKEN ---
    if os.path.exists(token_path):
        try:
            token_data = load_encrypted_json(token_path)
            if token_data:
                # Check if the cached token has all currently required scopes
                token_scopes = token_data.get('scopes', [])
                missing_scopes = [s for s in SCOPES if s not in token_scopes]
                if missing_scopes:
                    print(f"🔄 Token is missing required scopes: {missing_scopes}. Forcing re-authorization...")
                    creds = None
                else:
                    creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            else:
                creds = None
        except Exception as e:
            print(f"❌ REAL ERROR LOADING TOKEN: {type(e).__name__}: {e}") # <--- This reveals the truth
            creds = None

    # --- STEP 2: CHECK VALIDITY & REFRESH ---
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Token expired. Refreshing automatically...")
            try:
                creds.refresh(Request())
            except Exception:
                print("❌ Refresh failed. Starting fresh login...")
                creds = None # Token is too broken, force re-login

        # --- STEP 3: RE-AUTHORIZE (The 'generate_token' replacement) ---
        if not creds:
            print("🚀 Initiating New Login... (Check your browser)")
            
            if not os.path.exists(credentials_path):
                print(f"❌ CRITICAL ERROR: credentials.json not found at {credentials_path}")
                print("You cannot login without this file. Please download it from Google Cloud Console.")
                return None

            try:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                # Tries port 8080 first (standard), then falls back to a random port
                try:
                    creds = flow.run_local_server(
                        port=9915,
                        access_type='offline', # Ask for offline access (refresh token)
                        prompt='consent'       # Force the consent screen to ensure we get it
                    )
                except Exception:
                    print("⚠️ Port 8080 blocked. Trying random port (Check console for Redirect Mismatch)...")
                    creds = flow.run_local_server(port=9260)
            except Exception as e:
                print(f"❌ Login Flow Failed: {e}")
                return None

        # --- STEP 4: SAVE THE NEW/REFRESHED TOKEN ---
        try:
            token_data = json.loads(creds.to_json())
            save_encrypted_json(token_path, token_data)
            print(f"✅ Credentials saved securely (encrypted) to: {token_path}")
        except Exception as e:
            print(f"⚠️ Could not save token: {e}")

    return creds




def get_stdin_prompt_banner(action_type: str, reason: str) -> str:
    """Introspects the call stack to identify the active worker and current subtask,
    returning a formatted terminal card layout.
    action_type can be 'PASSWORD' or 'INTERVENTION'
    """
    import inspect
    import textwrap
    import re
    
    agent_name = "System"
    active_task = "User query execution"
    current_step = reason
    
    stack = inspect.stack()
    for frame_info in stack:
        func_name = frame_info.function
        f_locals = frame_info.frame.f_locals
        
        if func_name in ["_run_ephemeral_agent", "_run_async_ephemeral_agent"]:
            w_name = f_locals.get("worker_name")
            t_desc = f_locals.get("task_desc")
            if w_name:
                agent_name = w_name
            if t_desc:
                active_task = t_desc
                
        if func_name in ["update_skill_tool", "run_terminal_tool", "run_python_tool", "terminate_process_tool"]:
            if func_name == "update_skill_tool":
                skill_name = f_locals.get("skill_name")
                current_step = f"Updating/Creating system skill: '{skill_name}'"
            elif func_name == "run_terminal_tool":
                cmd = f_locals.get("command")
                current_step = f"Executing terminal command: '{cmd}'"
            elif func_name == "run_python_tool":
                current_step = "Executing python code execution"

    if action_type == "PASSWORD":
        title = "🔒 PASSWORD AUTHORIZATION REQUIRED"
        color = "\033[1;31m" # Red
    else:
        title = "🚨 HUMAN INTERVENTION REQUESTED"
        color = "\033[1;33m" # Yellow
        
    reset = "\033[0m"
    cyan = "\033[1;36m"
    white = "\033[1;37m"
    
    inner_width = 76
    
    def visual_len(text):
        # Strip ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_text = ansi_escape.sub('', text)
        # Double-width characters in terminal (emojis used)
        double_width_chars = ["🤖", "📋", "❓", "💡", "🔒", "🚨"]
        extra = sum(1 for char in clean_text if char in double_width_chars)
        return len(clean_text) + extra

    def make_content_line(label, value_line):
        v_len_label = visual_len(label)
        v_len_val = visual_len(value_line)
        padding_len = inner_width - v_len_label - v_len_val
        if padding_len < 0:
            padding_len = 0
        return f"{label}{value_line}{' ' * padding_len}"

    # Labels have a visual length of exactly 19.
    label_agent = f" {cyan}🤖 Agent Asking:{reset}  "  # Space + emoji + " Agent Asking:  " (1 + 2 + 16 = 19)
    label_task =  f" {cyan}📋 Active Task:{reset}    "  # Space + emoji + " Active Task:    " (1 + 2 + 16 = 19)
    label_step =  f" {cyan}❓ Current Step:{reset}   "  # Space + emoji + " Current Step:   " (1 + 2 + 16 = 19)
    label_reason = f" {cyan}💡 Reason:{reset}         "  # Space + emoji + " Reason:         " (1 + 2 + 16 = 19)
    indent_spaces = " " * 19

    lines = []
    
    # 1. Title line
    v_len_title = visual_len(title) + 1  # 1 space prefix
    title_padding = inner_width - v_len_title
    title_line = f" {title}{' ' * title_padding}"
    lines.append(f"{color}│{reset}{title_line}{color}│{reset}")
    lines.append(f"{color}├{'─' * inner_width}┤{reset}")

    # Helper to wrap and build lines for a field
    def add_field(label, val):
        val_str = str(val).replace("\n", " ").strip()
        wrapped_vals = textwrap.wrap(val_str, width=57)  # 76 - 19 = 57
        if not wrapped_vals:
            wrapped_vals = [""]
        for i, line in enumerate(wrapped_vals):
            lbl = label if i == 0 else indent_spaces
            content = make_content_line(lbl, f"{white}{line}{reset}")
            lines.append(f"{color}│{reset}{content}{color}│{reset}")

    add_field(label_agent, agent_name)
    add_field(label_task, active_task)
    add_field(label_step, current_step)
    add_field(label_reason, reason)

    banner_lines = [
        f"{color}┌{'─' * inner_width}┐{reset}"
    ] + lines + [
        f"{color}└{'─' * inner_width}┘{reset}"
    ]
    return "\n" + "\n".join(banner_lines) + "\n"


def verify_password():
    """
    Prompts the user for a password to authorize sensitive actions.
    Reads SYSTEM_PASSWORD (or AGENT_PASSWORD) from root .env or config/.env.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    
    # Try root .env first, fallback to config/.env
    env_paths = [
        os.path.join(root_dir, ".env"),
        os.path.join(root_dir, "config", ".env")
    ]
    
    correct_password = None

    # Manually load .env to handle encodings
    for env_path in env_paths:
        if os.path.exists(env_path):
            for encoding in ['utf-8', 'utf-16', 'utf-8-sig', 'cp1252']:
                try:
                    with open(env_path, 'r', encoding=encoding) as f:
                        for line in f:
                            stripped = line.strip()
                            if stripped.startswith("SYSTEM_PASSWORD="):
                                correct_password = stripped.split("=", 1)[1].strip().strip("'").strip('"')
                                break
                            elif stripped.startswith("AGENT_PASSWORD="):
                                correct_password = stripped.split("=", 1)[1].strip().strip("'").strip('"')
                                break
                    if correct_password is not None:
                        break # Stop trying encodings if we found the key
                except UnicodeDecodeError:
                    continue
                except Exception:
                    continue
            if correct_password is not None:
                break # Stop searching other env paths if found

    if not correct_password:
        # Fallback to standard load if manual failed (or if key wasn't found)
        for env_path in env_paths:
            if os.path.exists(env_path):
                load_dotenv(env_path)
                correct_password = os.getenv("SYSTEM_PASSWORD") or os.getenv("AGENT_PASSWORD")
                if correct_password:
                    break

    if not correct_password:
        print("❌ Critical Security Block: SYSTEM_PASSWORD is not set in .env. Protected operations are denied.")
        return False

    with _stdin_lock:
        import sys
        import builtins
        vis = getattr(builtins, "active_cli_visualizer", None)
        was_active_and_not_paused = False
        if vis and vis.active and not vis.is_paused:
            was_active_and_not_paused = True
            vis.is_paused = True
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()
        elif vis and vis.active and vis.is_paused:
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

        try:
            banner = get_stdin_prompt_banner("PASSWORD", "Authentication verification needed")
            print(banner, flush=True)
            user_input = input("🔒 Enter Password to authorize action: ").strip()
            if user_input == correct_password:
                return True
            else:
                print("❌ Access Denied: Incorrect Password.")
                return False
        except Exception as e:
            print(f"Error during password verification: {e}")
            return False
        finally:
            if was_active_and_not_paused and vis and vis.active:
                vis.is_paused = False