from typing import Optional
from langchain_core.tools import tool
from modules.workers.google_drive_worker.integrations.drive_client import (
    list_drive_files as _list_files,
    download_drive_file as _download_file,
    upload_drive_file as _upload_file,
    create_drive_folder as _create_folder,
    delete_drive_file as _delete_file,
    get_drive_about as _get_about
)

@tool
def list_drive_files_tool(query: Optional[str] = None, limit: int = 10, account: str = "personal") -> str:
    """Lists/searches files on Google Drive."""
    res = _list_files(query=query, limit=limit, account=account)
    files = res.get("files", [])
    if not files:
        return f"No files found matching query '{query}' on account '{account}'."
    lines = [f"Found {len(files)} files on account '{account}':"]
    for f in files:
        lines.append(f"- {f.get('name')} (ID: {f.get('id')}, Type: {f.get('mimeType')})")
    return "\n".join(lines)

@tool
def download_drive_file_tool(file_id: str, local_destination_path: str, account: str = "personal") -> str:
    """Downloads a file from Google Drive to a local disk path."""
    return str(_download_file(file_id=file_id, local_destination_path=local_destination_path, account=account))

@tool
def upload_drive_file_tool(local_file_path: str, folder_id: Optional[str] = None, new_name: Optional[str] = None, account: str = "personal") -> str:
    """Uploads a local file to Google Drive."""
    return str(_upload_file(local_file_path=local_file_path, folder_id=folder_id, new_name=new_name, account=account))

@tool
def create_drive_folder_tool(folder_name: str, parent_folder_id: Optional[str] = None, account: str = "personal") -> str:
    """Creates a new folder on Google Drive."""
    return str(_create_folder(folder_name=folder_name, parent_folder_id=parent_folder_id, account=account))

@tool
def delete_drive_file_tool(file_id: str, permanent: bool = False, account: str = "personal") -> str:
    """Deletes or trashes a file on Google Drive."""
    return str(_delete_file(file_id=file_id, permanent=permanent, account=account))

@tool
def get_drive_about_tool(account: str = "personal") -> str:
    """Retrieves Google Drive storage usage statistics and account info."""
    return str(_get_about(account=account))

drive_tools = [
    list_drive_files_tool,
    download_drive_file_tool,
    upload_drive_file_tool,
    create_drive_folder_tool,
    delete_drive_file_tool,
    get_drive_about_tool
]
