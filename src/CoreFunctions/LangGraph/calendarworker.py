from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import calendar_tools

def create_calendar_worker(model):
    """
    Creates the CalendarWorker node.
    """
    system_prompt = (
        "You are the CalendarWorker. "
        "Your capabilities include managing Google Tasks and Calendar events. "
        "Use 'add_google_task' to create to-do items. "
        "Use 'check_calendar_events' to see what's on the schedule. "
        "Use 'add_calendar_event' to schedule new meetings or events. "
        "Assume the current date and time is available via system tools if needed, but focus on the scheduling actions."
    )

    worker = WorkerAgent(
        model=model,
        tools=calendar_tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node()
