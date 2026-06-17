from src.CoreFunctions.StateGraph.registry import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.ClassroomWorker.classroom_prompt import SYSTEM_PROMPT
from src.CoreFunctions.StateGraph.Workers.ClassroomWorker.classroom_tools import classroom_tools

@WorkerRegistry.register
class ClassroomWorker(BaseWorker):
    name = "ClassroomWorker"
    description = "Manages Google Classroom courses, coursework, assignments, and announcements."
    instructions = SYSTEM_PROMPT
    tools = classroom_tools
    categories = ["academic", "education", "ClassroomWorker"]
