import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Classroom.classroom_ops import get_coursework_details

def fetch_classroom_assignment_details(course_id: str, coursework_id: str, account: str = "personal") -> str:
    """Retrieves full details for a specific Google Classroom coursework (assignment) ID.

    Args:
        course_id (str): The Classroom course ID.
        coursework_id (str): The specific assignment ID.
        account (str): The target Google account, either 'personal', 'college', or 'both'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_classroom_assignment_details")
    print(f"   Args: course_id={course_id}, coursework_id={coursework_id}, account={account}")
    try:
        res = get_coursework_details(course_id, coursework_id, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error fetching coursework details: {e}"

classroom_worker_tool_fetch_assignment_details = StructuredTool.from_function(
    func=fetch_classroom_assignment_details,
    name="fetch_classroom_assignment_details",
    description="Retrieves full details for a specific Google Classroom coursework (assignment) ID."
)
