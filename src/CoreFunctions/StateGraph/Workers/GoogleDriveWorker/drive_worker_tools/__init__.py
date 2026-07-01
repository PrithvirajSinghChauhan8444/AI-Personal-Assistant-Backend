from src.CoreFunctions.SharedTools import human_intervention_tool
from .drive_worker_tool_list_files import list_drive_files_tool
from .drive_worker_tool_download_file import download_drive_file_tool
from .drive_worker_tool_upload_file import upload_drive_file_tool
from .drive_worker_tool_create_folder import create_drive_folder_tool
from .drive_worker_tool_delete_file import delete_drive_file_tool
from .drive_worker_tool_get_about import get_drive_about_tool

drive_tools = [
    list_drive_files_tool,
    download_drive_file_tool,
    upload_drive_file_tool,
    create_drive_folder_tool,
    delete_drive_file_tool,
    get_drive_about_tool,
    human_intervention_tool
]
