from googleapiclient.discovery import build
from src.CoreFunctions.Infrastructure.auth_utils import get_valid_credentials

def get_classroom_service(account: str = "personal"):
    """Authenticates and returns the Google Classroom API service for a specific account."""
    creds = get_valid_credentials(account)
    if not creds:
        raise Exception(f"Google API credentials authentication failed for account '{account}'.")
    return build('classroom', 'v1', credentials=creds)
