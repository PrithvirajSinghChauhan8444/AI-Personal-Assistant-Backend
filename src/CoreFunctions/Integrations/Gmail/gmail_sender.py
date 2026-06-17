import os
import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from CoreFunctions.auth_utils import get_valid_credentials

def get_gmail_service():
    """Authenticates and returns the Gmail service object."""
    creds = get_valid_credentials("personal")
    if not creds:
        raise Exception("Google credentials could not be loaded or authorized.")
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