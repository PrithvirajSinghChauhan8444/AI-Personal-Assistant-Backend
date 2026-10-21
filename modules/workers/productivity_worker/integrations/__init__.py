"""Calendar and Tasks integrations for productivity_worker."""
from .calendar_client import (
    get_calendar_service,
    list_calendar_events,
    create_calendar_event,
    delete_calendar_event
)
from .tasks_client import (
    get_tasks_service,
    list_tasks,
    add_task
)

__all__ = [
    "get_calendar_service",
    "list_calendar_events",
    "create_calendar_event",
    "delete_calendar_event",
    "get_tasks_service",
    "list_tasks",
    "add_task"
]
