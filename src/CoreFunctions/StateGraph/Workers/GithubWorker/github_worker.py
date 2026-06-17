from src.CoreFunctions.StateGraph.registry import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.GithubWorker.github_prompt import SYSTEM_PROMPT
from src.CoreFunctions.StateGraph.Workers.GithubWorker.github_tools import github_tools

@WorkerRegistry.register
class GithubWorker(BaseWorker):
    name = "GithubWorker"
    description = "Interfaces with GitHub API to retrieve details, list repos, branches, commits, events, and search code."
    instructions = SYSTEM_PROMPT
    tools = github_tools
    categories = ["development", "dev-utils", "GithubWorker"]
