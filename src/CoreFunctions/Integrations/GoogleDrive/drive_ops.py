import os
import io
import sys
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from src.CoreFunctions.Infrastructure.auth_utils import get_valid_credentials

def get_drive_service(account: str = "personal"):
    """Authenticates and returns the Google Drive API service client for a specific account."""
    creds = get_valid_credentials(account)
    if not creds:
        raise Exception(f"Google API authentication failed for account '{account}'.")
    return build('drive', 'v3', credentials=creds)

def list_drive_files(query: str = None, limit: int = 10, account: str = "personal") -> dict:
    """
    Lists/searches files on Google Drive.
    
    Args:
        query (str): The search query (e.g. 'name contains "report"', 'mimeType = "application/vnd.google-apps.folder"').
        limit (int): The maximum number of results to return.
        account (str): The Google account, 'personal' or 'college'.
    """
    try:
        service = get_drive_service(account)
        results = service.files().list(
            q=query,
            pageSize=limit,
            fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, parents)"
        ).execute()
        
        files = results.get('files', [])
        return {
            "count": len(files),
            "files": files
        }
    except Exception as e:
        print(f"Error listing Drive files: {e}")
        return {"error": str(e)}

def download_drive_file(file_id: str, local_path: str, account: str = "personal") -> str:
    """
    Downloads a file from Google Drive by file ID.
    Supports automatically exporting Google Docs, Sheets, and Slides to standard open formats.
    
    Args:
        file_id (str): The Google Drive file ID.
        local_path (str): The local path where the file should be saved.
        account (str): The Google account, 'personal' or 'college'.
    """
    try:
        service = get_drive_service(account)
        
        # 1. Fetch file metadata to determine mimeType and name
        metadata = service.files().get(fileId=file_id, fields='name, mimeType').execute()
        mime_type = metadata.get('mimeType', '')
        name = metadata.get('name', '')
        
        # 2. Check if it's a Google Workspace App document that requires exporting
        google_apps_exports = {
            'application/vnd.google-apps.document': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx'),
            'application/vnd.google-apps.spreadsheet': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'),
            'application/vnd.google-apps.presentation': ('application/pdf', '.pdf'),
        }
        
        fh = io.BytesIO()
        
        if mime_type in google_apps_exports:
            export_mime, ext = google_apps_exports[mime_type]
            print(f"Exporting Google Workspace Document ({mime_type}) to {export_mime}...")
            
            # Ensure local_path ends with the correct extension
            if not local_path.endswith(ext):
                local_path += ext
                
            request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            request = service.files().get_media(fileId=file_id)
            
        # 3. Stream/Download chunks
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Download Progress: {int(status.progress() * 100)}%")
                
        # 4. Save to local disk
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(fh.getvalue())
            
        return f"Successfully downloaded file '{name}' to '{local_path}'."
    except Exception as e:
        print(f"Error downloading Drive file: {e}")
        return f"Error: {e}"

def upload_drive_file(local_path: str, name: str = None, parent_id: str = None, account: str = "personal") -> dict:
    """
    Uploads a local file to Google Drive.
    
    Args:
        local_path (str): The local file path to upload.
        name (str): The optional name of the file on Google Drive.
        parent_id (str): The optional folder ID on Google Drive to place the file inside.
        account (str): The Google account, 'personal' or 'college'.
    """
    try:
        if not os.path.exists(local_path):
            return {"error": f"Local file not found at: {local_path}"}
            
        service = get_drive_service(account)
        
        file_metadata = {'name': name or os.path.basename(local_path)}
        if parent_id:
            file_metadata['parents'] = [parent_id]
            
        media = MediaFileUpload(local_path, resumable=True)
        file_obj = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, mimeType'
        ).execute()
        
        return {
            "status": "success",
            "file": file_obj
        }
    except Exception as e:
        print(f"Error uploading Drive file: {e}")
        return {"error": str(e)}

def create_drive_folder(name: str, parent_id: str = None, account: str = "personal") -> dict:
    """
    Creates a folder in Google Drive.
    
    Args:
        name (str): The name of the folder.
        parent_id (str): The optional parent folder ID.
        account (str): The Google account, 'personal' or 'college'.
    """
    try:
        service = get_drive_service(account)
        
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]
            
        folder = service.files().create(
            body=file_metadata,
            fields='id, name'
        ).execute()
        
        return {
            "status": "success",
            "folder": folder
        }
    except Exception as e:
        print(f"Error creating folder: {e}")
        return {"error": str(e)}

def delete_drive_file(file_id: str, account: str = "personal") -> str:
    """
    Trashes/deletes a file or folder from Google Drive by ID.
    
    Args:
        file_id (str): The Google Drive file ID.
        account (str): The Google account, 'personal' or 'college'.
    """
    try:
        service = get_drive_service(account)
        # Update trashed attribute to True
        service.files().update(fileId=file_id, body={'trashed': True}).execute()
        return f"Successfully moved file/folder with ID '{file_id}' to the Trash bin."
    except Exception as e:
        print(f"Error trashing Drive file {file_id}: {e}")
        return f"Error: {e}"

def get_drive_about(account: str = "personal") -> dict:
    """
    Retrieves Google Drive storage quota details and user info.
    
    Args:
        account (str): The Google account, 'personal' or 'college'.
    """
    try:
        service = get_drive_service(account)
        about = service.about().get(fields="storageQuota, user").execute()
        
        quota = about.get("storageQuota", {})
        user = about.get("user", {})
        
        limit = int(quota.get("limit", 0))
        usage = int(quota.get("usage", 0))
        usage_in_drive = int(quota.get("usageInDrive", 0))
        usage_in_trash = int(quota.get("usageInDriveTrash", 0))
        
        free_space = max(0, limit - usage)
        
        def format_size(size_bytes: int) -> str:
            size_bytes = float(size_bytes)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.2f} PB"
            
        return {
            "status": "success",
            "user": {
                "display_name": user.get("displayName"),
                "email_address": user.get("emailAddress")
            },
            "storage_raw": {
                "limit_bytes": limit,
                "usage_bytes": usage,
                "usage_in_drive_bytes": usage_in_drive,
                "usage_in_drive_trash_bytes": usage_in_trash,
                "free_space_bytes": free_space
            },
            "storage_formatted": {
                "limit": format_size(limit),
                "usage_total": format_size(usage),
                "usage_in_drive": format_size(usage_in_drive),
                "usage_in_drive_trash": format_size(usage_in_trash),
                "free_space": format_size(free_space),
                "usage_percentage": f"{(usage / limit) * 100:.2f}%" if limit > 0 else "0.00%"
            }
        }
    except Exception as e:
        print(f"Error fetching Drive about info: {e}")
        return {"error": str(e)}
