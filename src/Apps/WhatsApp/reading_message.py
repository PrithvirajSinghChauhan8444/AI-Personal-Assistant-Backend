import requests
from .config import BASE_URL, get_headers

def get_chats(session_name="default"):
    """
    Fetches list of active chats to find Recipient IDs.
    Useful for finding Group IDs or checking recent contacts.
    """
    try:
        url = f"{BASE_URL}/api/chats?session={session_name}"
        response = requests.get(url, headers=get_headers())
        
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

def read_messages(session_name="default", limit=10):
    """
    Placeholder for reading messages.
    """
    return "Functionality to read messages not yet implemented."
