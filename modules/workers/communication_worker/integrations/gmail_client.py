import json
from typing import Dict, Any, List, Optional
from googleapiclient.discovery import build
from modules.infrastructure.security.oauth import get_google_credentials

def get_gmail_service(account: str = "personal"):
    """Authenticates and returns the Google Gmail API client for the account."""
    creds = get_google_credentials(account)
    if not creds:
        raise Exception(f"Google API authentication failed for account '{account}'.")
    return build('gmail', 'v1', credentials=creds)

def search_emails(query: str = "is:unread", max_results: int = 5, account: str = "personal") -> Dict[str, Any]:
    """Searches emails matching query string and returns list with headers and snippets."""
    try:
        from src.CoreFunctions.Integrations.Gmail.gmail_ops import search_gmail_metadata
        res = search_gmail_metadata(query=query, max_results=max_results, account=account)
        if isinstance(res, str):
            try:
                return json.loads(res)
            except Exception:
                return {"emails": [], "raw": res}
        return res if isinstance(res, dict) else {"emails": []}
    except Exception as e:
        service = get_gmail_service(account)
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])
        emails = []
        for msg in messages:
            m = service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
            headers = {h['name'].lower(): h['value'] for h in m.get('payload', {}).get('headers', [])}
            emails.append({
                "id": msg['id'],
                "sender": headers.get('from', 'Unknown'),
                "subject": headers.get('subject', 'No Subject'),
                "date": headers.get('date', ''),
                "snippet": m.get('snippet', '')
            })
        return {"emails": emails}

def read_email(message_id: str, account: str = "personal", page: int = 1, page_size: int = 2000) -> Dict[str, Any]:
    """Reads cleaned email body, headers, and attachments."""
    try:
        from src.CoreFunctions.Integrations.Gmail.gmail_ops import read_gmail_email
        return read_gmail_email(message_id=message_id, account=account, page=page, page_size=page_size)
    except Exception:
        service = get_gmail_service(account)
        msg = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        return {
            "id": message_id,
            "snippet": msg.get("snippet", ""),
            "threadId": msg.get("threadId", "")
        }

def send_email(to: str, subject: str, body: str, account: str = "personal") -> str:
    """Sends an email via Gmail API."""
    from src.CoreFunctions.Integrations.Gmail.gmail_sender import send_gmail_email
    return send_gmail_email(to=to, subject=subject, body=body, account=account)

def create_draft(to: str, subject: str, body: str, account: str = "personal") -> str:
    """Creates a draft email in the user's Gmail account."""
    from src.CoreFunctions.Integrations.Gmail.gmail_sender import create_gmail_draft
    return create_gmail_draft(to=to, subject=subject, body=body, account=account)

def reply_email(message_id: str, body: str, reply_all: bool = False, account: str = "personal") -> str:
    """Replies to an existing email thread."""
    from src.CoreFunctions.Integrations.Gmail.gmail_sender import reply_to_gmail_thread
    return reply_to_gmail_thread(message_id=message_id, body=body, reply_all=reply_all, account=account)
