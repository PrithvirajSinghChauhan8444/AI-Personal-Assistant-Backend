from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import calendar_tools, system_info_tools

def create_productivity_worker(model):
    """
    Creates the ProductivityWorker node.
    Combines Calendar, Google Tasks, and Weather capabilities.
    """
    system_prompt = (
        "You are the ProductivityWorker, an intelligent assistant focused on personal organization and daily planning. "
        "Your capabilities include:"
        "- Scheduling: Managing calendar events (viewing and adding).\n"
        "- Task Management: Handling to-do items via Google Tasks.\n"
        "- Environmental Awareness: Checking the weather forecast.\n"
        "You have access to a suite of productivity and system information tools. "
        "When a user request involves their schedule, tasks, or planning around weather conditions, "
        "analyze the needs and autonomously select the right tools. "
        "For example, if asked to 'schedule a run if it's sunny', check the weather first, then add the event. "
        "Confirm actions clearly."
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
