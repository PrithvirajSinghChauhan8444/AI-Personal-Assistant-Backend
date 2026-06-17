from langchain_core.tools import StructuredTool
from src.CoreFunctions.tools import (
    request_human_intervention_sync, request_human_intervention,
    get_github_profile_tool, list_github_repos_tool, get_github_recent_activity_tool,
    list_github_commits_tool, list_github_branches_tool, get_github_file_content_tool,
    search_github_code_tool
)

human_intervention_tool = StructuredTool.from_function(
    func=request_human_intervention_sync,
    name="request_human_intervention",
    description="Pauses the automated process and requests manual intervention from the human user. Use this when you hit CAPTCHAs, bot checks, 2FA prompts, or roadblocks/issues you cannot solve yourself.",
    coroutine=request_human_intervention
)

github_tools = [
    StructuredTool.from_function(get_github_profile_tool, name="get_github_profile"),
    StructuredTool.from_function(list_github_repos_tool, name="list_github_repos"),
    StructuredTool.from_function(get_github_recent_activity_tool, name="get_github_recent_activity"),
    StructuredTool.from_function(list_github_commits_tool, name="list_github_commits"),
    StructuredTool.from_function(list_github_branches_tool, name="list_github_branches"),
    StructuredTool.from_function(get_github_file_content_tool, name="get_github_file_content"),
    StructuredTool.from_function(search_github_code_tool, name="search_github_code"),
    human_intervention_tool
]
