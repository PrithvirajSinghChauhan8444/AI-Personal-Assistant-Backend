import sys
import os
from googleapiclient.discovery import build

# --- PATH FIX ---
# 1. Get the folder of this file (.../src/Apps/Calendar)
current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Go up two levels to reach 'src'
#    Level 1: .../src/Apps
#    Level 2: .../src
src_dir = os.path.dirname(os.path.dirname(current_dir))

# 3. Add 'src' to the system path so we can import CoreFunctions
if src_dir not in sys.path:
    sys.path.append(src_dir)

# --- IMPORTS ---
from CoreFunctions.auth_utils import get_valid_credentials

def get_service():
    """
    Connects to Google Calendar and returns the service object.
    """
    creds = get_valid_credentials()
    
    if not creds:
        print("❌ Auth failed: No credentials found.")
        return None

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None