from typing import Dict, Any, List, Optional
from googleapiclient.discovery import build
from modules.infrastructure.security.oauth import get_google_credentials
from src.CoreFunctions.Integrations.GoogleDrive.drive_ops import (
    list_drive_files as _list_files,
    download_drive_file as _download_file,
    upload_drive_file as _upload_file,
    create_drive_folder as _create_folder,
    delete_drive_file as _delete_file,
    get_drive_about as _get_about
)

def get_drive_service(account: str = "personal"):
    """Authenticates and returns the Google Drive API service client."""
    creds = get_google_credentials(account)
    if not creds:
        raise Exception(f"Google Drive authentication failed for account '{account}'.")
    return build('drive', 'v3', credentials=creds)

def list_drive_files(query: Optional[str] = None, limit: int = 10, account: str = "personal") -> dict:
    return _list_files(query=query, limit=limit, account=account)

def download_drive_file(file_id: str, local_destination_path: str, account: str = "personal") -> str:
    return _download_file(file_id=file_id, local_destination_path=local_destination_path, account=account)

def upload_drive_file(local_file_path: str, folder_id: Optional[str] = None, new_name: Optional[str] = None, account: str = "personal") -> dict:
    return _upload_file(local_file_path=local_file_path, folder_id=folder_id, new_name=new_name, account=account)

def create_drive_folder(folder_name: str, parent_folder_id: Optional[str] = None, account: str = "personal") -> dict:
    return _create_folder(folder_name=folder_name, parent_folder_id=parent_folder_id, account=account)

def delete_drive_file(file_id: str, permanent: bool = False, account: str = "personal") -> dict:
    return _delete_file(file_id=file_id, permanent=permanent, account=account)

def get_drive_about(account: str = "personal") -> dict:
    return _get_about(account=account)
