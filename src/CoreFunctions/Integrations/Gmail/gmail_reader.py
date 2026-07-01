import json
import re
import base64
from .gmail_service import get_gmail_service
from .email_cleaner import clean_body_content
from .job_store import create_email_job

def clean_sender(sender_str):
    if not sender_str:
        return "(Unknown Sender)"
    match = re.search(r'(.*)<(.*)>', sender_str)
    if match:
        name = match.group(1).strip().strip('"')
        email = match.group(2).strip()
        return f"{name} ({email})" if name else email
    return sender_str

def extract_body(payload):
    """Recursively extracts text/plain or text/html body from Gmail message payload."""
    if 'parts' in payload:
        for part in payload['parts']:
            body = extract_body(part)
            if body:
                return body
    elif payload.get('mimeType') == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    elif payload.get('mimeType') == 'text/html':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    return ""

def get_attachments_meta(payload, attachments=None):
    """Recursively scans payload parts to extract attachment metadata."""
    if attachments is None:
        attachments = []
    if 'parts' in payload:
        for part in payload['parts']:
            get_attachments_meta(part, attachments)
    else:
        filename = payload.get('filename')
        body = payload.get('body', {})
        attachment_id = body.get('attachmentId')
        if filename and attachment_id:
            attachments.append({
                "attachmentId": attachment_id,
                "filename": filename,
                "mimeType": payload.get('mimeType'),
                "size": body.get('size')
            })
    return attachments

def search_gmail_emails(query: str, max_results: int = 10, page_token: str = None, account: str = "personal") -> dict:
    """
    Search for emails in the user's Gmail mailbox using Gmail query syntax.
    
    Args:
        query (str): The search query (e.g. 'from:example@gmail.com', 'subject:meeting', 'is:unread').
        max_results (int): The maximum number of results to return.
        page_token (str): Page token for pagination.
        account (str): The specific account ('personal' or 'college').
    """
    try:
        service = get_gmail_service(account)
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results,
            pageToken=page_token
        ).execute()

        messages = results.get('messages', [])
        next_page_token = results.get('nextPageToken', None)

        if not messages:
            return {"count": 0, "emails": [], "nextPageToken": None}

        email_list = []
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='minimal').execute()
            headers = msg_data.get('payload', {}).get('headers', [])
            
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "(No Subject)")
            sender_raw = next((h['value'] for h in headers if h['name'].lower() == 'from'), None)
            date_raw = next((h['value'] for h in headers if h['name'].lower() == 'date'), None)
            
            sender = clean_sender(sender_raw)

            email_list.append({
                "id": msg_data['id'],
                "sender": sender,
                "subject": subject,
                "date": date_raw,
                "snippet": msg_data.get('snippet', '')
            })

        return {
            "count": len(email_list),
            "emails": email_list,
            "nextPageToken": next_page_token
        }
    except Exception as e:
        print(f"Error searching emails for {account}: {e}")
        return {"error": str(e)}

def fetch_email_ids(query: str, account: str = "personal") -> dict:
    """
    Find all message IDs matching a query and return a paginated job reference.
    
    Args:
        query (str): Gmail search query.
        account (str): Account name ('personal' or 'college').
    """
    try:
        service = get_gmail_service(account)
        all_ids = []
        page_token = None
        
        while True:
            results = service.users().messages().list(
                userId='me',
                q=query,
                pageToken=page_token,
                fields="messages/id,nextPageToken"
            ).execute()
            
            messages = results.get('messages', [])
            all_ids.extend([m['id'] for m in messages if 'id' in m])
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        # Create SQLite job entry
        job_info = create_email_job(query, all_ids, account)
        return job_info
    except Exception as e:
        print(f"Error fetching email IDs for {account}: {e}")
        return {"error": str(e)}

def read_gmail_email(email_id: str, account: str = "personal") -> dict:
    """
    Retrieve the full detailed contents of a specific email, including the complete body.
    
    Args:
        email_id (str): The unique ID of the Gmail message.
        account (str): The specific account ('personal' or 'college').
    """
    try:
        service = get_gmail_service(account)
        msg_data = service.users().messages().get(userId='me', id=email_id, format='full').execute()
        
        headers = msg_data.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "(No Subject)")
        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "(Unknown Sender)")
        date = next((h['value'] for h in headers if h['name'].lower() == 'date'), "(No Date)")
        to = next((h['value'] for h in headers if h['name'].lower() == 'to'), "(Unknown Recipient)")
        
        body = extract_body(msg_data.get('payload', {}))
        if body:
            body = clean_body_content(body)
        else:
            body = clean_body_content(msg_data.get('snippet', '(No Body Content)'))

        attachments = get_attachments_meta(msg_data.get('payload', {}))

        return {
            "id": email_id,
            "sender": clean_sender(sender),
            "to": to,
            "subject": subject,
            "date": date,
            "body": body,
            "threadId": msg_data.get('threadId', ''),
            "attachments": attachments
        }
    except Exception as e:
        print(f"Error reading email {email_id} for {account}: {e}")
        return {"error": str(e)}

def get_unread_count(account: str = "personal") -> dict:
    """
    Get the unread messages and threads counts for a specific Gmail account.
    
    Args:
        account (str): The specific account ('personal' or 'college').
    """
    try:
        service = get_gmail_service(account)
        label_info = service.users().labels().get(userId='me', id='UNREAD').execute()
        return {
            "unread_messages": label_info.get("messagesUnread", 0),
            "unread_threads": label_info.get("threadsUnread", 0)
        }
    except Exception as e:
        return {"error": str(e)}

def fetch_unread_emails_detailed(limit: int = 5, page_token: str = None, account: str = "personal") -> dict:
    """Fetches unread emails with full body parsing and content cleaning (composite/bulk)."""
    try:
        search_res = search_gmail_emails("is:unread", limit, page_token, account)
        if "error" in search_res or not search_res.get("emails"):
            return search_res
            
        detailed_emails = []
        for email_meta in search_res["emails"]:
            detailed = read_gmail_email(email_meta["id"], account)
            if "error" not in detailed:
                detailed_emails.append(detailed)
                
        return {
            "count": len(detailed_emails),
            "emails": detailed_emails,
            "nextPageToken": search_res.get("nextPageToken")
        }
    except Exception as e:
        return {"error": f"Failed to fetch detailed unread emails: {e}"}
