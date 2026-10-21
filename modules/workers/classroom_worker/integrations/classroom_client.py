from typing import Dict, Any, List, Optional
from googleapiclient.discovery import build
from modules.infrastructure.security.oauth import get_google_credentials
from src.CoreFunctions.Integrations.Classroom.classroom_ops import (
    list_courses as _list_courses,
    list_coursework as _list_coursework,
    get_coursework_details as _get_coursework_details,
    list_announcements as _list_announcements
)

def get_classroom_service(account: str = "personal"):
    """Authenticates and returns the Google Classroom API service client."""
    creds = get_google_credentials(account)
    if not creds:
        raise Exception(f"Google Classroom authentication failed for account '{account}'.")
    return build('classroom', 'v1', credentials=creds)

def list_courses(account: str = "personal") -> dict:
    return _list_courses(account=account)

def list_coursework(course_id: str, account: str = "personal") -> dict:
    return _list_coursework(course_id=course_id, account=account)

def get_coursework_details(course_id: str, coursework_id: str, account: str = "personal") -> dict:
    return _get_coursework_details(course_id=course_id, coursework_id=coursework_id, account=account)

def list_announcements(course_id: str, account: str = "personal") -> dict:
    return _list_announcements(course_id=course_id, account=account)

def download_coursework_materials(course_id: str, coursework_id: str, destination_dir: str = "/home/prit/Project_Linux/Assistant_Foler", account: str = "personal") -> str:
    try:
        from src.CoreFunctions.Integrations.Classroom.classroom_file_ops import download_classroom_materials
        return download_classroom_materials(course_id=course_id, coursework_id=coursework_id, destination_dir=destination_dir, account=account)
    except Exception as e:
        return f"Error downloading materials: {e}"

def submit_coursework(course_id: str, coursework_id: str, attachment_file_paths: list = None, account: str = "personal") -> str:
    try:
        from src.CoreFunctions.Integrations.Classroom.classroom_file_ops import submit_classroom_assignment
        return submit_classroom_assignment(course_id=course_id, coursework_id=coursework_id, file_paths=attachment_file_paths or [], account=account)
    except Exception as e:
        return f"Error submitting coursework: {e}"
