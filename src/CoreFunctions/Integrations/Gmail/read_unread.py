import re
from datetime import datetime
from googleapiclient.discovery import build
from CoreFunctions.auth_utils import get_valid_credentials

def fetch_unread_emails_detailed(page_token=None):
    # This one line handles EVERYTHING (checking, refreshing, re-logging in)
    creds = get_valid_credentials() 
    
    if not creds:
        return {"error": "Failed to get credentials."}

    service = build('gmail', 'v1', credentials=creds)
    # ... rest of your code ...

# --- Helper Functions ---
def clean_sender(sender_str):
    if not sender_str:
        return "(Unknown Sender)"
    match = re.search(r'(.*)<(.*)>', sender_str)
    if match:
        name = match.group(1).strip().strip('"')
        email = match.group(2).strip()
        return f"{name} ({email})" if name else email
    return sender_str

def parse_date(date_str):
    if not date_str:
        return "(No Date)"
    try:
        # Tries to parse standard Gmail date format
        date_obj = datetime.strptime(date_str.split(' (')[0].strip(), '%a, %d %b %Y %H:%M:%S %z')
        return date_obj.strftime('%d %b %Y %I:%M %p')
    except ValueError:
        return date_str

# --- Main Function ---
def fetch_unread_emails_detailed(page_token=None):
    """
    Fetches a page of unread Gmail messages (up to 10).
    Returns a dictionary with 'emails', 'count', and 'nextPageToken'.
    """
    
    # 1. NEW AUTH METHOD: Auto-refreshing credentials
    creds = get_valid_credentials()
    
    if not creds:
        return {"error": "Authentication failed. Token is missing or invalid."}

    try:
        service = build('gmail', 'v1', credentials=creds)

        # 2. IMPROVED SEARCH: Use q='is:unread' to find ALL unread mail
        results = service.users().messages().list(
            userId='me', 
            q='is:unread',      # Finds emails in Inbox, Updates, Promotions, etc.
            maxResults=10, 
            pageToken=page_token
        ).execute()
        
        messages = results.get('messages', [])
        next_page_token = results.get('nextPageToken', None)
        
        if not messages:
            return {"count": 0, "emails": [], "nextPageToken": None}

        email_list = []
        
        # 3. Fetch details for each message
        for msg in messages: 
            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            
            headers = msg_data['payload']['headers']
            
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "(No Subject)")
            sender_raw = next((h['value'] for h in headers if h['name'].lower() == 'from'), None)
            date_raw = next((h['value'] for h in headers if h['name'].lower() == 'date'), None)
            
            email_id = msg_data['id']
            snippet = msg_data.get('snippet', '(No Snippet)')
            
            sender = clean_sender(sender_raw)
            formatted_date = parse_date(date_raw)

            email_list.append({
                "id": email_id,
                "sender": sender,
                "subject": subject,
                "datetime": formatted_date,
                "content": snippet
            })

        return {
            "count": len(email_list), 
            "emails": email_list, 
            "nextPageToken": next_page_token
        }

    except Exception as e:
        print(f"Gmail API Error: {e}")
        return {"error": str(e)}