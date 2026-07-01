import base64
import os
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from .gmail_service import get_gmail_service

def send_gmail_email(to_address: str, subject: str, body_text: str, account: str = "personal") -> str:
    """Creates and sends an email.
    
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

def create_gmail_draft(to_address: str, subject: str, body_text: str, account: str = "personal") -> str:
    """Creates a draft email in the user's mailbox.
    
    Args:
        to_address (str): The recipient's email address.
        subject (str): The subject line of the email.
        body_text (str): The plain text content of the draft.
        account (str): The specific account ('personal' or 'college').
    """
    try:
        service = get_gmail_service(account)
        message = MIMEText(body_text)
        message['to'] = to_address
        message['from'] = 'me'
        message['subject'] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        body = {
            'draft': {
                'message': {
                    'raw': raw_message
                }
            }
        }
        
        print(f"Creating draft for {to_address} using account '{account}'...")
        response = service.users().drafts().create(userId='me', body=body).execute()
        return f"Successfully created draft on account '{account}'. Draft ID: {response.get('id')}"
    except Exception as e:
        return f"Error creating draft on account '{account}': {e}"

def send_gmail_with_attachment(to: str, subject: str, body: str, attachment_paths: list, account: str = "personal") -> str:
    """Sends an email with one or more local file attachments from a specific Gmail account.
    
    Args:
        to (str): The recipient's email address.
        subject (str): The email subject.
        body (str): The body text of the email.
        attachment_paths (list): A list of local file paths to attach.
        account (str): The target Google account ('personal' or 'college').
    """
    try:
        service = get_gmail_service(account)
        
        # Create a multipart message container
        message = MIMEMultipart()
        message['to'] = to
        message['from'] = 'me'
        message['subject'] = subject
        
        # Attach the body text
        message.attach(MIMEText(body, 'plain'))
        
        # Process and attach each file
        for file_path in attachment_paths:
            file_path = file_path.strip()
            if not os.path.exists(file_path):
                return f"❌ Attachment Error: File not found at '{file_path}'"
                
            filename = os.path.basename(file_path)
            content_type, encoding = mimetypes.guess_type(file_path)
            
            if content_type is None or encoding is not None:
                content_type = 'application/octet-stream'
                
            main_type, sub_type = content_type.split('/', 1)
            
            with open(file_path, 'rb') as fp:
                msg = MIMEBase(main_type, sub_type)
                msg.set_payload(fp.read())
                
            # Encode in base64 and add headers
            encoders.encode_base64(msg)
            msg.add_header('Content-Disposition', 'attachment', filename=filename)
            message.attach(msg)
            
        # Encode raw message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        body_dict = {'raw': raw_message}
        
        print(f"Sending email with {len(attachment_paths)} attachment(s) to {to} using account '{account}'...")
        response = service.users().messages().send(userId='me', body=body_dict).execute()
        return f"Successfully sent email to {to} on account '{account}' with attachments. Message ID: {response.get('id')}"
    except Exception as e:
        return f"Error sending email with attachments on account '{account}': {e}"
