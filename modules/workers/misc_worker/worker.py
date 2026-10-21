from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.infrastructure.llm_provider.llm_factory import get_llm, extract_text_content
from .prompts import MISC_WORKER_PROMPT
from .tools import tools

class MiscWorker(BaseWorkerProtocol):
    """Independent Misc Worker module for custom integrations and YouTube Music playlist management."""
    name = "MiscWorker"
    description = "General-purpose worker for miscellaneous integrations, YouTube Music playlist management, and custom scripts."
    instructions = MISC_WORKER_PROMPT
    tools = tools
    categories = ["general", "misc", "playlists", "MiscWorker"]

    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.0, llm_client: Optional[Any] = None):
        self._llm = llm_client or get_llm(model_name=model_name, temperature=temperature)
        self._agent = create_react_agent(self._llm, self.tools, prompt=self.instructions)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "Any requests to manage playlists (creating, adding songs, removing songs, listing library/favorite songs) on YouTube Music or run custom standalone scripts should be routed to MiscWorker."
        ]

    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Task: {description}"
        if context.get("working_memory"):
            prompt += f"\nAvailable Context: {context['working_memory']}"
        try:
            result = self._agent.invoke({"messages": [HumanMessage(content=prompt)]})
            messages = result.get("messages", [])
            last_msg = extract_text_content(messages[-1].content) if messages else "Misc execution completed."
            return {
                "status": "completed",
                "summary": last_msg,
                "data": {"misc_task_result": last_msg}
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": f"MiscWorker execution failed: {e}",
                "data": {},
                "error_message": str(e)
            }

if __name__ == "__main__":
    import sys
    task_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "List YouTube Music playlists"
    print(f"\n🚀 Running MiscWorker standalone...")
    print(f"Task: {task_desc}\n")
    worker = MiscWorker()
    output = worker.execute_task("standalone_misc_1", task_desc, {})
    print(f"Status : {output['status']}")
    print(f"Summary: {output['summary']}")
    if output.get("error_message"):
        print(f"Error  : {output['error_message']}")
