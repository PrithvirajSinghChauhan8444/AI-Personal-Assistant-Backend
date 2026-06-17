import base64
import os
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from CoreFunctions.Integrations.Gmail.gmail_ops import get_gmail_service

def download_gmail_attachment(email_id: str, attachment_id: str, filename: str, save_dir: str = "./Downloads", account: str = "personal") -> str:
    """Downloads a specific attachment from a Gmail email message.
    
    Args:
        email_id (str): The unique ID of the Gmail message.
        attachment_id (str): The unique ID of the attachment.
        filename (str): The name to save the file as (e.g. 'invoice.pdf').
        save_dir (str): The directory to save the file to. Defaults to './Downloads'.
        account (str): The target Google account ('personal' or 'college').
    """
    try:
        service = get_gmail_service(account)
        os.makedirs(save_dir, exist_ok=True)
        
        # Call the Gmail API to get the attachment content
        attachment = service.users().messages().attachments().get(
            userId='me',
            messageId=email_id,
            id=attachment_id
        ).execute()
        
        # The data is base64url encoded
        file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
        
        full_path = os.path.abspath(os.path.join(save_dir, filename))
        with open(full_path, 'wb') as f:
            f.write(file_data)
            
        return f"Successfully downloaded attachment '{filename}' to: {full_path}"
    except Exception as e:
        return f"Failed to download Gmail attachment: {e}"

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
