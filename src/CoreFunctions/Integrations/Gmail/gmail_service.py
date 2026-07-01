from googleapiclient.discovery import build
from src.CoreFunctions.Infrastructure.auth_utils import get_valid_credentials

def get_gmail_service(account: str = "personal"):
    """Authenticates and returns the Gmail API service for a specific account.
    
    Args:
        account (str): The Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    creds = get_valid_credentials(account)
    if not creds:
        raise Exception(f"Google API authentication failed for account '{account}'.")
    return build('gmail', 'v1', credentials=creds)
