from src.CoreFunctions.SharedTools import human_intervention_tool, run_terminal_tool_wrapped, run_python_tool_wrapped, get_time_tool, get_weather_tool, web_search_tool
from src.CoreFunctions.StateGraph.Workers.MemoryWorker.memory_worker_tools import memory_worker_tool_list_active_workers
from .system_worker_tool_launch_app import launch_app_tool
from .system_worker_tool_get_volume import get_audio_volume
from .system_worker_tool_set_volume import set_audio_volume
from .system_worker_tool_mute_toggle import mute_audio_toggle
from .system_worker_tool_get_brightness import get_screen_brightness
from .system_worker_tool_set_brightness import set_screen_brightness
from .system_worker_tool_control_media import control_media_player
from .system_worker_tool_list_running_processes import list_running_processes_tool
from .system_worker_tool_terminate_process import terminate_process_tool
from .system_worker_tool_lock_screen import lock_desktop_screen
from .system_worker_tool_suspend_system import suspend_desktop_system
from .system_worker_tool_copy_to_clipboard import copy_to_clipboard_tool
from .system_worker_tool_paste_from_clipboard import paste_from_clipboard_tool
from .system_worker_tool_download_url import download_url_tool
from .system_worker_tool_schedule_delayed_task import schedule_delayed_task_tool
from .system_worker_tool_schedule_task_at_time import schedule_task_at_time_tool
from .system_worker_tool_list_scheduled_tasks import list_scheduled_tasks_tool
from .system_worker_tool_cancel_scheduled_task import cancel_scheduled_task_tool
from .system_worker_tool_create_file import create_file_tool
from .system_worker_tool_read_file import read_file_tool
from .system_worker_tool_list_files import list_files_tool
from .system_worker_tool_create_dir import create_dir_tool
from .system_worker_tool_save_code import save_code_tool
from .system_worker_tool_index_directory import index_directory_tool
from .system_worker_tool_search_files_semantically import search_files_semantically_tool
from .system_worker_tool_rag_file_qa import rag_file_qa_tool
from .system_worker_tool_get_system_health import system_worker_tool_get_system_health

system_tools = [
    run_terminal_tool_wrapped,
    run_python_tool_wrapped,
    launch_app_tool,
    get_audio_volume,
    set_audio_volume,
    mute_audio_toggle,
    get_screen_brightness,
    set_screen_brightness,
    control_media_player,
    list_running_processes_tool,
    terminate_process_tool,
    lock_desktop_screen,
    suspend_desktop_system,
    copy_to_clipboard_tool,
    paste_from_clipboard_tool,
    download_url_tool,
    schedule_delayed_task_tool,
    schedule_task_at_time_tool,
    list_scheduled_tasks_tool,
    cancel_scheduled_task_tool,
    create_file_tool,
    read_file_tool,
    list_files_tool,
    create_dir_tool,
    save_code_tool,
    index_directory_tool,
    search_files_semantically_tool,
    rag_file_qa_tool,
    system_worker_tool_get_system_health,
    get_weather_tool,
    get_time_tool,
    web_search_tool,
    memory_worker_tool_list_active_workers,
    human_intervention_tool
]
