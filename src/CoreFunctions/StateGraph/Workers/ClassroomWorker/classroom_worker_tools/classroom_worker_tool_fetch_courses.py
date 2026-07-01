import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Classroom.classroom_ops import list_courses

def fetch_classroom_courses(account: str = "personal") -> str:
    """Lists the Google Classroom courses that the user is enrolled in or teaching.

    Args:
        account (str): The target Google account, either 'personal', 'college', or 'both' to fetch from both accounts. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_classroom_courses")
    print(f"   Args: account={account}")
    try:
        res = list_courses(account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error listing courses: {e}"

classroom_worker_tool_fetch_courses = StructuredTool.from_function(
    func=fetch_classroom_courses,
    name="fetch_classroom_courses",
    description="Lists the Google Classroom courses that the user is enrolled in or teaching."
)
