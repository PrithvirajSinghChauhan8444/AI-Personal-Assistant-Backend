from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Classroom.classroom_file_ops import download_classroom_materials

def download_classroom_materials_tool(course_id: str, coursework_id: str, save_dir: str = "/home/prit/Project_Linux/Assistant_Foler", account: str = "personal") -> str:
    """Downloads all attachments/materials associated with a Google Classroom assignment.
    
    Args:
        course_id (str): The Classroom course ID.
        coursework_id (str): The coursework (assignment) ID.
        save_dir (str): Local directory to save materials. Defaults to '/home/prit/Project_Linux/Assistant_Foler'.
        account (str): The Google account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: download_classroom_materials")
    try:
        return download_classroom_materials(course_id, coursework_id, save_dir, account)
    except Exception as e:
        return f"Error downloading classroom materials: {e}"

classroom_worker_tool_download_materials = StructuredTool.from_function(
    func=download_classroom_materials_tool,
    name="download_classroom_materials",
    description="Downloads all attachments/materials associated with a Google Classroom assignment."
)
