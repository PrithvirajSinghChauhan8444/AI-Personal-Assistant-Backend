import os
import base64
from .gmail_service import get_gmail_service

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
