import base64
from email.mime.text import MIMEText
from .gmail_service import get_gmail_service

def reply_to_gmail_email(email_id: str, body_text: str, account: str = "personal") -> str:
    """Reply to an email thread. Resolution of thread headers (In-Reply-To, References, subject) is done automatically.
    
    Args:
        email_id (str): The unique ID of the original email to reply to.
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
