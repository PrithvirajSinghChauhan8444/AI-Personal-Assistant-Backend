import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from CoreFunctions.auth_utils import get_valid_credentials
from CoreFunctions.Integrations.Classroom.classroom_ops import get_classroom_service
from CoreFunctions.Integrations.System.download_ops import download_file

def get_drive_service(account: str = "personal"):
    """Authenticates and returns the Google Drive API service for a specific account."""
    creds = get_valid_credentials(account)
    if not creds:
        raise Exception(f"Google API credentials authentication failed for account '{account}'.")
    return build('drive', 'v3', credentials=creds)

def download_drive_file(file_id: str, dest_path: str, account: str = "personal") -> str:
    """Downloads a file from Google Drive by its file ID.
    
    Args:
        file_id (str): The Google Drive file ID.
        dest_path (str): The local destination path to write the downloaded file.
        account (str): The Google account to use.
    """
    try:
        drive_service = get_drive_service(account)
        request = drive_service.files().get_media(fileId=file_id)
        
        with open(dest_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
        return f"Successfully downloaded Drive file to: {dest_path}"
    except Exception as e:
        return f"Failed to download from Google Drive: {e}"

def upload_file_to_drive(file_path: str, account: str = "personal") -> str:
    """Uploads a local file to Google Drive (in root folder) and returns the Drive file ID.
    
    Args:
        file_path (str): The path to the local file to upload.
        account (str): The Google account to use.
    """
    try:
        drive_service = get_drive_service(account)
        filename = os.path.basename(file_path)
        
        file_metadata = {
            'name': filename
        }
        
        media = MediaFileUpload(file_path, resumable=True)
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        return file.get('id')
    except Exception as e:
        raise Exception(f"Failed to upload file to Google Drive: {e}")

def download_classroom_materials(course_id: str, coursework_id: str, save_dir: str = "./Downloads", account: str = "personal") -> str:
    """Downloads all attachments/materials associated with a Google Classroom coursework (assignment).
    
    Args:
        course_id (str): The Classroom course ID.
        coursework_id (str): The coursework (assignment) ID.
        save_dir (str): Local directory to save materials. Defaults to './Downloads'.
        account (str): The target Google account ('personal' or 'college').
    """
    try:
        service = get_classroom_service(account)
        os.makedirs(save_dir, exist_ok=True)
        
        # Get coursework details
        item = service.courses().courseWork().get(courseId=course_id, id=coursework_id).execute()
        materials = item.get('materials', [])
        
        if not materials:
            return f"No materials found for coursework '{item.get('title', coursework_id)}'."
            
        results = []
        for idx, mat in enumerate(materials, 1):
            if 'driveFile' in mat:
                df = mat['driveFile']['driveFile']
                file_id = df['id']
                title = df.get('title', f"material_{idx}")
                dest_path = os.path.join(save_dir, title)
                res = download_drive_file(file_id, dest_path, account)
                results.append(f"Drive File: {res}")
            elif 'link' in mat:
                link = mat['link']
                url = link['url']
                title = link.get('title')
                res = download_file(url, save_dir, filename=title)
                results.append(f"Link: {res}")
            elif 'youtubeVideo' in mat:
                yt = mat['youtubeVideo']
                results.append(f"YouTube Video Link: {yt.get('title')} -> {yt.get('alternateLink')}")
            elif 'form' in mat:
                form = mat['form']
                results.append(f"Form Link: {form.get('title')} -> {form.get('formUrl')}")
                
        return "\n".join(results)
    except Exception as e:
        return f"Error downloading classroom materials: {e}"

def submit_classroom_assignment(course_id: str, coursework_id: str, file_paths: list, account: str = "personal") -> str:
    """Uploads files to Google Drive, attaches them to the student's Classroom submission, and turns it in.
    
    Args:
        course_id (str): The Classroom course ID.
        coursework_id (str): The coursework (assignment) ID.
        file_paths (list): A list of local file paths to submit.
        account (str): The target Google account ('personal' or 'college').
    """
    try:
        service = get_classroom_service(account)
        
        # 1. Fetch student submission ID
        submissions_res = service.courses().courseWork().studentSubmissions().list(
            courseId=course_id,
            courseWorkId=coursework_id,
            userId='me'
        ).execute()
        
        submissions = submissions_res.get('studentSubmissions', [])
        if not submissions:
            return "❌ Error: No student submission object found for this assignment."
            
        submission_id = submissions[0]['id']
        
        # 2. Upload each file to Drive and compile attachments list
        attachments = []
        for fp in file_paths:
            fp = fp.strip()
            if not os.path.exists(fp):
                return f"❌ Error: Submission file not found at '{fp}'."
            
            print(f"Uploading '{os.path.basename(fp)}' to Google Drive...")
            drive_id = upload_file_to_drive(fp, account)
            attachments.append({
                "driveFile": {
                    "id": drive_id
                }
            })
            
        # 3. Attach files to the student submission
        print(f"Attaching {len(attachments)} file(s) to coursework submission {submission_id}...")
        service.courses().courseWork().studentSubmissions().modifyAttachments(
            courseId=course_id,
            courseWorkId=coursework_id,
            id=submission_id,
            body={
                "addAttachments": attachments
            }
        ).execute()
        
        # 4. Turn in submission
        print(f"Turning in coursework submission {submission_id}...")
        service.courses().courseWork().studentSubmissions().turnIn(
            courseId=course_id,
            courseWorkId=coursework_id,
            id=submission_id
        ).execute()
        
        return f"Successfully uploaded and turned in assignment with {len(file_paths)} file(s)."
    except Exception as e:
        return f"Failed to submit Classroom assignment: {e}"
