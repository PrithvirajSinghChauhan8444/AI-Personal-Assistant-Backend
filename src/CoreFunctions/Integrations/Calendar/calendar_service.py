import sys
import os
from googleapiclient.discovery import build

# --- PATH FIX ---
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(current_dir))

if src_dir not in sys.path:
    sys.path.append(src_dir)

from CoreFunctions.auth_utils import get_valid_credentials

def get_service(account: str = "personal"):
    """
    Connects to Google Calendar and returns the service object for a specific account.
    """
    creds = get_valid_credentials(account)
    
    if not creds:
        print(f"❌ Auth failed: No credentials found for account '{account}'.")
        return None

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None