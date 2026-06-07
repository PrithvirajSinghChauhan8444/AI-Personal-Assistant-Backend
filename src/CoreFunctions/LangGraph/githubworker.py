from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import github_tools

def create_github_worker(model):
    """
    Creates the GithubWorker node.
    """
    system_prompt = (
        "You are the GithubWorker. Your role is GitHub account management (profile information, repositories, branch list, recent activity, and repository commit details).\n"
        "Analyze the request, select the best tool, and execute.\n"
        "Default Search Behavior: Unless the user explicitly specifies a different username, you MUST default to searching/listing repositories under your own authenticated account first (which checks both public and private repositories). Only search another user's public repositories if a different username is explicitly requested.\n"
        "Always report results clearly and concisely.\n\n"
        "### EXAMPLES\n"
        "User: 'Show my profile details'\n"
        "Action: calls `get_github_profile` -> 'User: octocat, Followers: 120, Repos: 45...'\n\n"
        "User: 'List my top 5 repositories'\n"
        "Action: calls `list_github_repos(count=5)` -> 'Found 5 repos: personal-site, dotfiles...'\n\n"
        "User: 'List all branches for my app repo'\n"
        "Action: calls `list_github_branches(repo_name='app')` -> 'Found branches: main, using-langraph, dev'\n\n"
        "User: 'Show recent commits for the project-x repository'\n"
        "Action: calls `list_github_commits(repo_name='project-x')` -> 'Recent commits: [c304fa3] Fixed bug in server; [a19cd30] Updated README...'\n\n"
        "User: 'What was my recent github activity?'\n"
        "Action: calls `get_github_recent_activity` -> 'Pushed 2 commits to main, Starred a repo...'"
    )

    worker = WorkerAgent(
        model=model,
        tools=github_tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node(name="GithubWorker")
