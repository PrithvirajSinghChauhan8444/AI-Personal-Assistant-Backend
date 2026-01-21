from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import calendar_tools

def create_calendar_worker(model):
    """
    Creates the CalendarWorker node.
    """
    system_prompt = (
        "You are the CalendarWorker, and you manage the user's schedule and tasks. "
        "Your capabilities include scheduling events, checking calendar availability, "
        "and managing to-do items on Google Tasks. "
        "You have access to tools that interface with the calendar and task services. "
        "When presented with a scheduling request, assess the requirements—such as time, duration, and participants—"
        "and employ the relevant instruments to fulfill the user's need. "
        "Feel free to query the calendar to avoid conflicts before adding new events. "
        "Explicitly confirm when items are added or modified."
    )

    worker = WorkerAgent(
        model=model,
        tools=calendar_tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node()
