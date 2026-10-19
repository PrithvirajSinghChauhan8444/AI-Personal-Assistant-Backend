from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.workers.productivity_worker.tools.productivity_tools import productivity_tools
from modules.infrastructure.llm_provider.llm_factory import get_llm, extract_text_content

class ProductivityWorker(BaseWorkerProtocol):
    """Independent Productivity Worker for Calendar, Tasks, and Scheduling."""
    name = "ProductivityWorker"
    description = "Schedules events, checks calendar availability, and tracks to-do tasks."
    instructions = "You are the ProductivityWorker. You manage schedules, calendar events, tasks, and time checks."
    tools = productivity_tools
    categories = ["productivity", "calendar", "tasks"]

    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.0, llm_client: Optional[Any] = None):
        self._llm = llm_client or get_llm(model_name=model_name, temperature=temperature)
        self._agent = create_react_agent(self._llm, self.tools, prompt=self.instructions)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "Any calendar queries, meeting scheduling, task additions, or time checks must route to ProductivityWorker."
        ]

    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Task: {description}"
        if context.get("working_memory"):
            prompt += f"\nContext: {context['working_memory']}"
        try:
            result = self._agent.invoke({"messages": [HumanMessage(content=prompt)]})
            messages = result.get("messages", [])
            last_msg = extract_text_content(messages[-1].content) if messages else "Productivity task finished."
            return {
                "status": "completed",
                "summary": last_msg,
                "data": {"productivity_task_result": last_msg}
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": f"ProductivityWorker execution failed: {e}",
                "data": {},
                "error_message": str(e)
            }

if __name__ == "__main__":
    import sys
    task_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is the current time and calendar schedule?"
    print(f"\n🚀 Running ProductivityWorker standalone...")
    print(f"Task: {task_desc}\n")
    worker = ProductivityWorker()
    output = worker.execute_task("standalone_prod_1", task_desc, {})
    print(f"Status : {output['status']}")
    print(f"Summary: {output['summary']}")
    if output.get("error_message"):
        print(f"Error  : {output['error_message']}")
