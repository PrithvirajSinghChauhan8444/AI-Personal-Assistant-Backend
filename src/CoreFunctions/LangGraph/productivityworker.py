from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import calendar_tools, system_info_tools

def create_productivity_worker(model):
    """
    Creates the ProductivityWorker node.
    Combines Calendar, Google Tasks, and Weather capabilities.
    """
    system_prompt = (
        "You are the ProductivityWorker. Your role is personal organization (Calendar, Tasks, Weather).\n"
        "Analyze the request, select the best tool, and execute.\n"
        "Always report results clearly and concisely.\n\n"
        "### EXAMPLES\n"
        "User: 'What is on my calendar today?'\n"
        "Action: calls `list_calendar_events` -> 'You have 2 events today: Meeting at 10 AM, Gym at 5 PM.'\n\n"
        "User: 'Add a task to buy milk'\n"
        "Action: calls `add_task(title='Buy milk')` -> 'Task \"Buy milk\" added to your list.'\n\n"
        "User: 'Is it going to rain?'\n"
        "Action: calls `get_weather(location='current')` -> 'The forecast shows clear skies, no rain expected.'"
    )
    
    # Combine tools: Calendar/Tasks + Weather (subset of system_info)
    # Extracting specifically weather tool if needed, or just giving all system_info tools is fine too.
    # Let's give all system_info as it includes time too, which is creating for scheduling.
    tools = calendar_tools + system_info_tools

    worker = WorkerAgent(
        model=model,
        tools=tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node(name="ProductivityWorker")
