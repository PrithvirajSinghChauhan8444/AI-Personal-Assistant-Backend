from src.CoreFunctions.SharedTools import human_intervention_tool
from .github_worker_tool_get_profile import get_github_profile
from .github_worker_tool_list_repos import list_github_repos
from .github_worker_tool_get_recent_activity import get_github_recent_activity
from .github_worker_tool_list_commits import list_github_commits
from .github_worker_tool_list_branches import list_github_branches
from .github_worker_tool_get_file_content import get_github_file_content
from .github_worker_tool_search_code import search_github_code

github_tools = [
    get_github_profile,
    list_github_repos,
    get_github_recent_activity,
    list_github_commits,
    list_github_branches,
    get_github_file_content,
    search_github_code,
    human_intervention_tool
]
