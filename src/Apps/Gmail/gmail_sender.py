import os
import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from CoreFunctions.path_utils import get_config_path

def get_gmail_service():
    """Authenticates and returns the Gmail service object."""
    token_path = get_config_path('token.json')
    if not os.path.exists(token_path):
        raise Exception("token.json not found. Please authenticate first.")
    
    creds = Credentials.from_authorized_user_file(token_path, [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/calendar'
    ])
    service = build('gmail', 'v1', credentials=creds)
    return service

def send_email(to_address, subject, body_text):
    """
    Creates and sends an email.
    
    Args:
        to_address (str): The recipient's email address.
        subject (str): The subject line of the email.
        body_text (str): The plain text content of the email.
    
    Returns:
        dict: The response from the Gmail API.
    """
    try:
        service = get_gmail_service()
        
        # 1. Create the MIMEText object
        message = MIMEText(body_text)
        message['to'] = to_address
        message['from'] = 'me' # 'me' is a special alias for the authenticated user
        message['subject'] = subject
        
        # 2. Encode the message in URL-safe base64
        # This is the required format for the API
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        body = {
            'raw': raw_message
        }
        
        # 3. Send the message
        print(f"Sending email to {to_address}...")
        send_response = service.users().messages().send(userId='me', body=body).execute()
        
        print(f"Email sent. Message ID: {send_response.get('id')}")
        return send_response

    except Exception as e:
        print(f"An error occurred while sending email: {e}")
        return {"error": str(e)}