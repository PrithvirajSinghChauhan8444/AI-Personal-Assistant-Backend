from langchain_core.tools import StructuredTool
from src.CoreFunctions.tools import (
    request_human_intervention_sync, request_human_intervention,
    add_google_task, check_calendar_events, add_calendar_event,
    get_system_health, get_weather, get_time, web_search
)

human_intervention_tool = StructuredTool.from_function(
    func=request_human_intervention_sync,
    name="request_human_intervention",
    description="Pauses the automated process and requests manual intervention from the human user. Use this when you hit CAPTCHAs, bot checks, 2FA prompts, or roadblocks/issues you cannot solve yourself.",
    coroutine=request_human_intervention
)

calendar_tools = [
    StructuredTool.from_function(add_google_task),
    StructuredTool.from_function(check_calendar_events),
    StructuredTool.from_function(add_calendar_event),
    StructuredTool.from_function(get_system_health),
    StructuredTool.from_function(get_weather),
    StructuredTool.from_function(get_time),
    StructuredTool.from_function(web_search),
    human_intervention_tool
]
