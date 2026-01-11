import requests
import os
import re
import time

# --- Configuration ---
BASE_URL = "http://localhost:8085"

def load_env_vars():
    """
    Load environment variables from .env file manually.
    Handles stripping quotes to prevent 'Unauthorized' errors.
    """
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    api_key = "secretKEY123" # Default fallback
    
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                # parsing logic: ignore comments, look for KEY=VALUE
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key == "WAHA_API_KEY":
                        # CRITICAL FIX: Strip whitespace AND quotes (' or ")
                        api_key = value.strip().strip('"').strip("'")
                        break
    return api_key

API_KEY = load_env_vars()

HEADERS = {
    "X-Api-Key": API_KEY,
    "Content-Type": "application/json"
}

# --- Helper Functions ---

def format_phone_number(phone):
    """
    Formats phone number to WAHA chat ID.
    - Removes non-digits.
    - Adds default country code '91' (India) if length is 10.
    """
    # If it already looks like an ID (contains @), return it as is
    if "@" in str(phone):
        return phone

    clean_number = re.sub(r'\D', '', str(phone))
    
    if len(clean_number) == 10:
        clean_number = '91' + clean_number
    
    return f"{clean_number}@c.us"

def start_session(session_name="default"):
    """Starts the session if it is currently STOPPED."""
    try:
        url = f"{BASE_URL}/api/sessions"
        # POST to /api/sessions creates or starts the session
        payload = {"name": session_name}
        requests.post(url, json=payload, headers=HEADERS)
        time.sleep(2) # Wait a moment for it to spin up
        return True
    except Exception as e:
        print(f"Error starting session: {e}")
        return False

# --- Main Tool Functions ---

def get_status(session_name="default"):
    """Checks connection status (CONNECTED, STOPPED, SCANNING_QR)."""
    try:
        url = f"{BASE_URL}/api/sessions?all=true"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            sessions = response.json()
            # Find our specific session
            for session in sessions:
                if session.get('name') == session_name:
                    return f"Status: {session.get('status', 'UNKNOWN')}"
            return "Session not found."
        return f"Error: {response.text}"
    except Exception as e:
        return f"Connection Failed: {e}"

def get_qr_code(session_name="default"):
    """Saves the QR code to a file so you can scan it."""
    try:
        # WAHA Screenshot endpoint returns the actual image buffer
        url = f"{BASE_URL}/api/screenshot?session={session_name}"
        # Only API Key header needed for GET image
        img_headers = {"X-Api-Key": API_KEY}
        
        response = requests.get(url, headers=img_headers)
        
        if response.status_code == 200:
            # Save to the current directory
            filename = "whatsapp_qr.png"
            file_path = os.path.abspath(filename)
            
            with open(file_path, "wb") as f:
                f.write(response.content)
            return f"✅ QR Code saved to: {file_path}\nPlease open this image and scan it with your phone."
        elif response.status_code == 404:
            return "❌ QR Code not available. Status might be 'CONNECTED' already."
        else:
            return f"❌ Error getting QR: {response.text}"
    except Exception as e:
        return f"Error: {e}"

def get_chats(session_name="default"):
    """
    Fetches list of active chats to find Recipient IDs.
    Useful for finding Group IDs or checking recent contacts.
    """
    try:
        url = f"{BASE_URL}/api/chats?session={session_name}"
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code == 200:
            chats = response.json()
            if not chats:
                return "No active chats found."
            
            # Format a nice list for the AI/User to read
            output = ["--- Active Chats List ---"]
            for chat in chats:
                name = chat.get('name', 'Unknown')
                c_id = chat.get('id')
                kind = "Group" if '@g.us' in c_id else "User"
                output.append(f"[{kind}] {name}  ->  ID: {c_id}")
            
            return "\n".join(output)
        else:
            return f"Failed to fetch chats: {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"

def send_message(phone, message, session_name="default"):
    """
    Sends a WhatsApp message.
    - phone: Can be '9876543210' OR '12036...@g.us'
    - message: Text string
    """
    try:
        chat_id = format_phone_number(phone)
        
        url = f"{BASE_URL}/api/sendText"
        payload = {
            "session": session_name,
            "chatId": chat_id,
            "text": message
        }
        
        response = requests.post(url, json=payload, headers=HEADERS)
        
        # Success Case
        if response.status_code == 201:
            return f"✅ Message sent to {chat_id}"
        
        # Handle 'Session Stopped' Error automatically
        if "STOPPED" in response.text:
            print("[System] Session stopped. Restarting...")
            start_session(session_name)
            # Retry sending once
            time.sleep(3) 
            response = requests.post(url, json=payload, headers=HEADERS)
            if response.status_code == 201:
                return f"✅ Message sent (after restart) to {chat_id}"
        
        return f"❌ Failed to send: {response.text}"
        
    except Exception as e:
        return f"❌ Error: {e}"

# --- Manual Test (Optional) ---
if __name__ == "__main__":
    print("1. Checking Status...")
    print(get_status())
    
    # print("\n2. Getting Chat IDs (Uncomment to test)...")
    # print(get_chats())
    
    # print("\n3. Sending Test Message (Uncomment to test)...")
    # print(send_message("9876543210", "Hello from Python!"))