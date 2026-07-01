import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Classroom.classroom_ops import list_announcements

def fetch_classroom_announcements(course_id: str, account: str = "personal") -> str:
    """Lists announcements for a specific Google Classroom course ID.

    Args:
        course_id (str): The unique course ID.
        account (str): The target Google account, either 'personal', 'college', or 'both'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_classroom_announcements")
    print(f"   Args: course_id={course_id}, account={account}")
    try:
        res = list_announcements(course_id, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error listing announcements: {e}"

classroom_worker_tool_fetch_announcements = StructuredTool.from_function(
    func=fetch_classroom_announcements,
    name="fetch_classroom_announcements",
    description="Lists announcements for a specific Google Classroom course ID."
)
