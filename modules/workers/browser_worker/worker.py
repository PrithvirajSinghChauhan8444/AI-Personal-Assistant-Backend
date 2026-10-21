from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.workers.browser_worker.tools import tools as browser_tools
from modules.workers.browser_worker.prompts import BROWSER_INSTRUCTIONS
from modules.infrastructure.llm_provider.llm_factory import get_llm, extract_text_content

class BrowserWorker(BaseWorkerProtocol):
    """Independent Browser Worker module for web navigation, web scraping, and UI interaction."""
    name = "BrowserWorker"
    description = "Navigates websites, searches the web, interacts with UI elements, clicks links, and scrapes web content."
    instructions = BROWSER_INSTRUCTIONS
    tools = browser_tools
    categories = ["browser", "web-automation", "scraping", "BrowserWorker"]

    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.0, llm_client: Optional[Any] = None):
        self._llm = llm_client or get_llm(model_name=model_name, temperature=temperature)
        self._agent = create_react_agent(self._llm, self.tools, prompt=self.instructions)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "Any tasks requiring opening URLs, navigating web pages, clicking links, inspecting live web pages, filling online forms, or interacting with browser web applications must be routed to BrowserWorker."
        ]

    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Task: {description}"
        if context.get("working_memory"):
            prompt += f"\nAvailable Context: {context['working_memory']}"
        try:
            result = self._agent.invoke({"messages": [HumanMessage(content=prompt)]})
            messages = result.get("messages", [])
            last_msg = extract_text_content(messages[-1].content) if messages else "Browser execution completed."
            return {
                "status": "completed",
                "summary": last_msg,
                "data": {"browser_task_result": last_msg}
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": f"BrowserWorker execution failed: {e}",
                "data": {},
                "error_message": str(e)
            }

if __name__ == "__main__":
    import sys
    task_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Check Wikipedia homepage title"
    print(f"\n🚀 Running BrowserWorker standalone...")
    print(f"Task: {task_desc}\n")
    worker = BrowserWorker()
    output = worker.execute_task("standalone_browser_1", task_desc, {})
    print(f"Status : {output['status']}")
    print(f"Summary: {output['summary']}")
    if output.get("error_message"):
        print(f"Error  : {output['error_message']}")
