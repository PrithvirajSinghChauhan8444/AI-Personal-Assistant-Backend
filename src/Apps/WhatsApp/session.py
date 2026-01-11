import requests
import time
import os
from .config import BASE_URL, get_headers, API_KEY

def start_session(session_name="default"):
    """Starts the session if it is currently STOPPED."""
    try:
        url = f"{BASE_URL}/api/sessions/{session_name}/start"
        # POST to /api/sessions creates or starts the session
        payload = {"name": session_name}
        requests.post(url, json=payload, headers=get_headers())
        time.sleep(2) # Wait a moment for it to spin up
        return True
    except Exception as e:
        print(f"Error starting session: {e}")
        return False

def get_status(session_name="default"):
    """Checks connection status (CONNECTED, STOPPED, SCANNING_QR)."""
    try:
        url = f"{BASE_URL}/api/sessions?all=true"
        response = requests.get(url, headers=get_headers())
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
