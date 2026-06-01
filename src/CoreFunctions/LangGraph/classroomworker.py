from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import classroom_tools

def create_classroom_worker(model):
    """
    Creates the ClassroomWorker node.
    """
    system_prompt = (
        "You are ClassroomWorker. You are specialized in synchronizing and fetching Google Classroom courses, coursework, assignments, and announcements.\n"
        "Your available tools are:\n"
        "- `fetch_classroom_courses`: Lists the Google Classroom courses the user is enrolled in.\n"
        "- `fetch_classroom_assignments`: Lists coursework/assignments for a given course ID.\n"
        "- `fetch_classroom_announcements`: Lists announcements for a given course ID.\n"
        "- `fetch_classroom_assignment_details`: Gets detailed metadata for a specific course assignment.\n\n"
        "Always execute tasks accurately, fetch the requested academic details, and return them clearly."
    )

    worker = WorkerAgent(
        model=model,
        tools=classroom_tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node(name="ClassroomWorker")
