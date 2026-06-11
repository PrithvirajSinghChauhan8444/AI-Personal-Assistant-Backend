import base64
import re
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from CoreFunctions.auth_utils import get_valid_credentials

def get_gmail_service(account: str = "personal"):
    """Authenticates and returns the Gmail API service for a specific account."""
    creds = get_valid_credentials(account)
    if not creds:
        raise Exception(f"Google API authentication failed for account '{account}'.")
    return build('gmail', 'v1', credentials=creds)

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
    """Recursively extracts text/plain body from Gmail message payload."""
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
        # Fallback to HTML if plain text isn't found in this part
        data = payload.get('body', {}).get('data', '')
        if data:
            # Basic strip tags for LLM readability
            html = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            clean = re.sub(r'<[^>]+>', ' ', html)
            return re.sub(r'\s+', ' ', clean).strip()
    return ""

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
        if not body:
            body = msg_data.get('snippet', '(No Body Content)')

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

def trash_gmail_email(email_id: str, account: str = "personal") -> str:
    """
    Move a specific email message to the Trash folder.
    
    Args:
        email_id (str): The unique ID of the Gmail message to trash.
        account (str): The specific account ('personal' or 'college').
    """
    try:
        service = get_gmail_service(account)
        service.users().messages().trash(userId='me', id=email_id).execute()
        return f"Successfully moved email {email_id} to Trash on account '{account}'."
    except Exception as e:
        return f"Error trashing email: {e}"

def mark_gmail_as_read(email_id: str, account: str = "personal") -> str:
    """
    Mark an email message as read by removing the UNREAD label.
    
    Args:
        email_id (str): The unique ID of the Gmail message.
        account (str): The specific account ('personal' or 'college').
    """
    try:
        service = get_gmail_service(account)
        service.users().messages().batchModify(
            userId='me',
            body={
                'ids': [email_id],
                'removeLabelIds': ['UNREAD']
            }
        ).execute()
        return f"Successfully marked email {email_id} as read on account '{account}'."
    except Exception as e:
        return f"Error marking email as read: {e}"

def reply_to_gmail_email(email_id: str, body_text: str, account: str = "personal") -> str:
    """
    Reply to a specific email message, keeping it correctly threaded.
    
    Args:
        email_id (str): The ID of the email to reply to.
        body_text (str): The plain text content of your reply.
        account (str): The specific account ('personal' or 'college').
    """
    try:
        service = get_gmail_service(account)
        
        # 1. Fetch original message to get headers
        orig = service.users().messages().get(userId='me', id=email_id, format='full').execute()
        orig_headers = orig.get('payload', {}).get('headers', [])
        
        # Determine recipient of reply (original sender)
        orig_sender = next((h['value'] for h in orig_headers if h['name'].lower() == 'from'), None)
        orig_msg_id = next((h['value'] for h in orig_headers if h['name'].lower() == 'message-id'), None)
        orig_subject = next((h['value'] for h in orig_headers if h['name'].lower() == 'subject'), "")
        
        if not orig_sender:
            return "Error: Could not determine sender of original email."
            
        # Clean subject line
        subject = orig_subject
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
            
        thread_id = orig.get('threadId')
        
        # 2. Build reply
        message = MIMEText(body_text)
        message['to'] = orig_sender
        message['from'] = 'me'
        message['subject'] = subject
        
        if orig_msg_id:
            message['In-Reply-To'] = orig_msg_id
            message['References'] = orig_msg_id
            
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        body = {
            'raw': raw_message,
            'threadId': thread_id
        }
        
        print(f"Replying to {orig_sender} in thread {thread_id} using account '{account}'...")
        response = service.users().messages().send(userId='me', body=body).execute()
        return f"Successfully sent reply to thread {thread_id}. Message ID: {response.get('id')}"
        
    except Exception as e:
        return f"Error replying to email on account '{account}': {e}"

def send_gmail_email(to_address: str, subject: str, body_text: str, account: str = "personal") -> str:
    """
    Creates and sends an email.
    
    Args:
        to_address (str): The recipient's email address.
        subject (str): The subject line of the email.
        body_text (str): The plain text content of the email.
        account (str): The specific account ('personal' or 'college').
    """
    try:
        service = get_gmail_service(account)
        message = MIMEText(body_text)
        message['to'] = to_address
        message['from'] = 'me'
        message['subject'] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        body = {'raw': raw_message}
        
        print(f"Sending email to {to_address} using account '{account}'...")
        response = service.users().messages().send(userId='me', body=body).execute()
        return f"Successfully sent email to {to_address} on account '{account}'. Message ID: {response.get('id')}"
    except Exception as e:
        return f"Error sending email on account '{account}': {e}"
