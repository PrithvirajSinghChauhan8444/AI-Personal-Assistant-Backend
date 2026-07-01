from typing import List
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Classroom.classroom_file_ops import submit_classroom_assignment

def submit_classroom_assignment_tool(course_id: str, coursework_id: str, file_paths: List[str], account: str = "personal") -> str:
    """Uploads local files to Google Drive, attaches them to a Google Classroom coursework submission, and turns it in.
    
    Args:
        course_id (str): The Classroom course ID.
        coursework_id (str): The coursework (assignment) ID.
        file_paths (List[str]): A list of local file paths to upload and submit.
        account (str): The Google account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: submit_classroom_assignment")
    try:
        return submit_classroom_assignment(course_id, coursework_id, file_paths, account)
    except Exception as e:
        return f"Error submitting classroom assignment: {e}"

classroom_worker_tool_submit_assignment = StructuredTool.from_function(
    func=submit_classroom_assignment_tool,
    name="submit_classroom_assignment",
    description="Uploads local files to Google Drive, attaches them to a Google Classroom coursework submission, and turns it in."
)
