from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.workers.github_worker.tools import tools as github_tools
from modules.workers.github_worker.prompts import GITHUB_INSTRUCTIONS
from modules.infrastructure.llm_provider.llm_factory import get_llm, extract_text_content

class GithubWorker(BaseWorkerProtocol):
    """Independent Github Worker module for GitHub API interactions."""
    name = "GithubWorker"
    description = "Interfaces with GitHub API to retrieve details, list repositories, branches, commits, events, and search code."
    instructions = GITHUB_INSTRUCTIONS
    tools = github_tools
    categories = ["development", "dev-utils", "github", "GithubWorker"]

    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.0, llm_client: Optional[Any] = None):
        self._llm = llm_client or get_llm(model_name=model_name, temperature=temperature)
        self._agent = create_react_agent(self._llm, self.tools, prompt=self.instructions)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "Any tasks related to GitHub (such as listing repositories, searching code on GitHub, inspecting commits, checking pull requests, viewing GitHub branches or profile activity) must be routed to GithubWorker."
        ]

    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Task: {description}"
        if context.get("working_memory"):
            prompt += f"\nAvailable Context: {context['working_memory']}"
        try:
            result = self._agent.invoke({"messages": [HumanMessage(content=prompt)]})
            messages = result.get("messages", [])
            last_msg = extract_text_content(messages[-1].content) if messages else "GitHub execution completed."
            return {
                "status": "completed",
                "summary": last_msg,
                "data": {"github_task_result": last_msg}
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": f"GithubWorker execution failed: {e}",
                "data": {},
                "error_message": str(e)
            }

if __name__ == "__main__":
    import sys
    task_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "List my recent GitHub repositories"
    print(f"\n🚀 Running GithubWorker standalone...")
    print(f"Task: {task_desc}\n")
    worker = GithubWorker()
    output = worker.execute_task("standalone_github_1", task_desc, {})
    print(f"Status : {output['status']}")
    print(f"Summary: {output['summary']}")
    if output.get("error_message"):
        print(f"Error  : {output['error_message']}")
