from langchain_core.tools import StructuredTool
from src.CoreFunctions.tools import (
    request_human_intervention_sync, request_human_intervention,
    run_terminal_tool, run_python_tool, launch_app_tool,
    get_audio_volume, set_audio_volume, mute_audio_toggle,
    get_screen_brightness, set_screen_brightness, control_media_player,
    list_running_processes_tool, terminate_process_tool, lock_desktop_screen, suspend_desktop_system,
    copy_to_clipboard_tool, paste_from_clipboard_tool, download_url_tool,
    schedule_delayed_task_tool, schedule_task_at_time_tool,
    list_scheduled_tasks_tool, cancel_scheduled_task_tool,
    create_file_tool, read_file_tool, list_files_tool, 
    create_dir_tool, save_code_tool,
    index_directory_tool, search_files_semantically_tool, rag_file_qa_tool,
    get_system_health, get_weather, get_time, web_search,
    list_active_workers_tool
)

human_intervention_tool = StructuredTool.from_function(
    func=request_human_intervention_sync,
    name="request_human_intervention",
    description="Pauses the automated process and requests manual intervention from the human user. Use this when you hit CAPTCHAs, bot checks, 2FA prompts, or roadblocks/issues you cannot solve yourself.",
    coroutine=request_human_intervention
)

system_tools = [
    StructuredTool.from_function(run_terminal_tool),
    StructuredTool.from_function(run_python_tool),
    StructuredTool.from_function(launch_app_tool),
    StructuredTool.from_function(get_audio_volume),
    StructuredTool.from_function(set_audio_volume),
    StructuredTool.from_function(mute_audio_toggle),
    StructuredTool.from_function(get_screen_brightness),
    StructuredTool.from_function(set_screen_brightness),
    StructuredTool.from_function(control_media_player),
    StructuredTool.from_function(list_running_processes_tool),
    StructuredTool.from_function(terminate_process_tool),
    StructuredTool.from_function(lock_desktop_screen),
    StructuredTool.from_function(suspend_desktop_system),
    StructuredTool.from_function(copy_to_clipboard_tool),
    StructuredTool.from_function(paste_from_clipboard_tool),
    StructuredTool.from_function(download_url_tool),
    StructuredTool.from_function(schedule_delayed_task_tool),
    StructuredTool.from_function(schedule_task_at_time_tool),
    StructuredTool.from_function(list_scheduled_tasks_tool),
    StructuredTool.from_function(cancel_scheduled_task_tool),
    StructuredTool.from_function(create_file_tool),
    StructuredTool.from_function(read_file_tool),
    StructuredTool.from_function(list_files_tool),
    StructuredTool.from_function(create_dir_tool),
    StructuredTool.from_function(save_code_tool),
    StructuredTool.from_function(index_directory_tool),
    StructuredTool.from_function(search_files_semantically_tool),
    StructuredTool.from_function(rag_file_qa_tool),
    StructuredTool.from_function(get_system_health),
    StructuredTool.from_function(get_weather),
    StructuredTool.from_function(get_time),
    StructuredTool.from_function(web_search),
    StructuredTool.from_function(list_active_workers_tool),
    human_intervention_tool
]
