from typing import List, Optional
from langchain_core.tools import tool
from modules.workers.github_worker.integrations.github_client import (
    get_github_profile as _get_profile,
    list_github_repos as _list_repos,
    list_github_branches as _list_branches,
    list_github_commits as _list_commits,
    get_github_file_content as _get_file_content,
    search_github_code as _search_code,
    get_github_recent_activity as _get_activity
)

@tool
def get_profile_tool(username: Optional[str] = None) -> str:
    """Retrieves profile information for a GitHub user (or authenticated user if omitted)."""
    return str(_get_profile(username))

@tool
def list_repos_tool(username: Optional[str] = None, count: int = 10) -> str:
    """Lists repositories for a user (including private repositories for the authenticated user)."""
    return str(_list_repos(username=username, count=count))

@tool
def list_branches_tool(repo_name: str, owner: Optional[str] = None) -> str:
    """Lists branches in a specific GitHub repository."""
    return str(_list_branches(repo_name=repo_name, owner=owner))

@tool
def list_commits_tool(repo_name: str, branch: Optional[str] = None, count: int = 5, owner: Optional[str] = None) -> str:
    """Lists recent commits in a repository."""
    return str(_list_commits(repo_name=repo_name, branch=branch, count=count, owner=owner))

@tool
def get_file_content_tool(repo_name: str, file_path: str, branch: Optional[str] = None, owner: Optional[str] = None) -> str:
    """Retrieves file content from a GitHub repository."""
    return str(_get_file_content(repo_name=repo_name, file_path=file_path, branch=branch, owner=owner))

@tool
def search_code_tool(query: str, repo: Optional[str] = None, owner: Optional[str] = None) -> str:
    """Searches code on GitHub."""
    return str(_search_code(query=query, repo=repo, owner=owner))

@tool
def get_recent_activity_tool(username: Optional[str] = None, count: int = 5) -> str:
    """Retrieves recent GitHub activity and push events."""
    return str(_get_activity(username=username, count=count))

github_tools = [
    get_profile_tool,
    list_repos_tool,
    list_branches_tool,
    list_commits_tool,
    get_file_content_tool,
    search_code_tool,
    get_recent_activity_tool
]
