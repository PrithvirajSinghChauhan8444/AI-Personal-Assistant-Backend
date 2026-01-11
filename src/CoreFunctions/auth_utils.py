import os
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# The permissions your app needs
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
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
    # 1. Get the directory containing this script (src/CoreFunctions)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Go up one level to 'src'
    src_dir = os.path.dirname(current_dir)
    
    # 3. Go up one level to 'ROOT'
    root_dir = os.path.dirname(src_dir)
    
    # 4. Go into 'config'
    config_dir = os.path.join(root_dir, 'config')
    
    return config_dir

def get_valid_credentials():
    """
    The Master Auth Function.
    1. Checks if token exists and is valid.
    2. Auto-refreshes if expired.
    3. Auto-launches Browser Login if token is missing/dead.
    """
    config_dir = get_config_dir()
    print(config_dir)
    
    # Ensure config dir exists (sanity check)
    if not os.path.exists(config_dir):
        print(f"❌ Error: Config folder not found at: {config_dir}")
        return None

    token_path = os.path.join(config_dir, 'token.json')
    credentials_path = os.path.join(config_dir, 'credentials.json')

    creds = None

    # --- STEP 1: LOAD EXISTING TOKEN ---
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
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
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            print(f"✅ Credentials saved to: {token_path}")
        except Exception as e:
            print(f"⚠️ Could not save token (Permission error?): {e}")

    return creds




def verify_password():
    """
    Prompts the user for a password to authorize sensitive actions.
    Reads AGENT_PASSWORD from .env, handling potential encoding issues.
    """
    config_dir = get_config_dir()
    env_path = os.path.join(config_dir, ".env")
    correct_password = None

    # Manually load .env to handle encodings
    if os.path.exists(env_path):
        for encoding in ['utf-8', 'utf-16', 'utf-8-sig', 'cp1252']:
            try:
                with open(env_path, 'r', encoding=encoding) as f:
                    for line in f:
                        if line.strip().startswith("AGENT_PASSWORD="):
                            # Extract value after '=' and strip quotes/whitespace
                            correct_password = line.split("=", 1)[1].strip().strip("'").strip('"')
                            break # Found it
                if correct_password is not None:
                    break # Stop trying encodings if we found the key
            except UnicodeDecodeError:
                continue
            except Exception:
                continue

    if not correct_password:
        # Fallback to standard load if manual failed (or if key wasn't found)
        load_dotenv(env_path)
        correct_password = os.getenv("AGENT_PASSWORD")

    if not correct_password:
        print("⚠️ Warning: AGENT_PASSWORD not set in .env. Allowing action (Unsafe).")
        return True

    try:
        user_input = input("🔒 Enter Password to authorize action: ").strip()
        if user_input == correct_password:
            return True
        else:
            print("❌ Access Denied: Incorrect Password.")
            return False
    except Exception as e:
        print(f"Error during password verification: {e}")
        return False