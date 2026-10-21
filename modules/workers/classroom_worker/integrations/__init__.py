"""Google Classroom integrations for classroom_worker."""
from .classroom_client import (
    get_classroom_service,
    list_courses,
    list_coursework,
    get_coursework_details,
    list_announcements,
    download_coursework_materials,
    submit_coursework
)

__all__ = [
    "get_classroom_service",
    "list_courses",
    "list_coursework",
    "get_coursework_details",
    "list_announcements",
    "download_coursework_materials",
    "submit_coursework"
]
