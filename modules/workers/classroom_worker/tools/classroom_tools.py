from typing import Optional, List
from langchain_core.tools import tool
from modules.workers.classroom_worker.integrations.classroom_client import (
    list_courses as _list_courses,
    list_coursework as _list_coursework,
    get_coursework_details as _get_coursework_details,
    list_announcements as _list_announcements,
    download_coursework_materials as _download_materials,
    submit_coursework as _submit_coursework
)

@tool
def list_courses_tool(account: str = "both") -> str:
    """Lists courses the user is enrolled in or teaching across Google accounts ('personal', 'college', 'both')."""
    res = _list_courses(account=account)
    courses = res.get("courses", [])
    if not courses:
        return f"No Google Classroom courses found on account '{account}'."
    lines = [f"Found {len(courses)} Classroom courses:"]
    for c in courses:
        lines.append(f"- {c.get('name')} (ID: {c.get('id')}, Section: {c.get('section', 'N/A')})")
    return "\n".join(lines)

@tool
def list_assignments_tool(course_id: str, account: str = "personal") -> str:
    """Lists assignments and coursework for a specific course ID."""
    res = _list_coursework(course_id=course_id, account=account)
    coursework = res.get("coursework", [])
    if not coursework:
        return f"No assignments found for course ID '{course_id}'."
    lines = [f"Coursework for Course {course_id}:"]
    for cw in coursework:
        lines.append(f"- {cw.get('title')} (ID: {cw.get('id')}, Due: {cw.get('dueDate', 'No due date')})")
    return "\n".join(lines)

@tool
def get_assignment_details_tool(course_id: str, coursework_id: str, account: str = "personal") -> str:
    """Gets detailed instructions and materials for a specific assignment."""
    res = _get_coursework_details(course_id=course_id, coursework_id=coursework_id, account=account)
    return str(res)

@tool
def list_announcements_tool(course_id: str, account: str = "personal") -> str:
    """Lists teacher announcements for a course."""
    res = _list_announcements(course_id=course_id, account=account)
    return str(res)

@tool
def download_materials_tool(course_id: str, coursework_id: str, destination_dir: Optional[str] = None, account: str = "personal") -> str:
    """Downloads attached assignment materials to a local folder."""
    return str(_download_materials(course_id=course_id, coursework_id=coursework_id, destination_dir=destination_dir, account=account))

@tool
def submit_assignment_tool(course_id: str, coursework_id: str, attachment_file_paths: Optional[List[str]] = None, account: str = "personal") -> str:
    """Submits student coursework with optional file attachments."""
    return str(_submit_coursework(course_id=course_id, coursework_id=coursework_id, attachment_file_paths=attachment_file_paths, account=account))

classroom_tools = [
    list_courses_tool,
    list_assignments_tool,
    get_assignment_details_tool,
    list_announcements_tool,
    download_materials_tool,
    submit_assignment_tool
]
