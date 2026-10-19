from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.workers.communication_worker.tools.gmail_tools import gmail_tools
from modules.infrastructure.llm_provider.llm_factory import get_llm

class CommunicationWorker(BaseWorkerProtocol):
    """Independent Communication Worker for managing emails and message dispatches."""
    name = "GmailWorker"
    description = "Searches, reads, drafts, and sends emails via Gmail."
    instructions = "You are the GmailWorker. You inspect inboxes, fetch unread messages, and send or draft emails. Never make assumptions on email addresses."
    tools = gmail_tools
    categories = ["communication", "email", "gmail"]

    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.0, llm_client: Optional[Any] = None):
        self._llm = llm_client or get_llm(model_name=model_name, temperature=temperature)
        self._agent = create_react_agent(self._llm, self.tools, prompt=self.instructions)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "Any operations concerning reading emails, searching messages, or sending emails must route to GmailWorker."
        ]

    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Task: {description}"
        if context.get("working_memory"):
            prompt += f"\nContext: {context['working_memory']}"
        try:
            result = self._agent.invoke({"messages": [HumanMessage(content=prompt)]})
            messages = result.get("messages", [])
            last_msg = messages[-1].content if messages else "Email task finished."
            return {
                "status": "completed",
                "summary": str(last_msg),
                "data": {"gmail_task_result": str(last_msg)}
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": f"GmailWorker execution failed: {e}",
                "data": {},
                "error_message": str(e)
            }

if __name__ == "__main__":
    import sys
    task_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Fetch unread emails"
    print(f"\n🚀 Running CommunicationWorker standalone...")
    print(f"Task: {task_desc}\n")
    worker = CommunicationWorker()
    output = worker.execute_task("standalone_email_1", task_desc, {})
    print(f"Status : {output['status']}")
    print(f"Summary: {output['summary']}")
    if output.get("error_message"):
        print(f"Error  : {output['error_message']}")
