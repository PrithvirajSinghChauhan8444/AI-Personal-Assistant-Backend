from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.workers.communication_worker.tools import tools as communication_tools
from modules.workers.communication_worker.prompts import COMMUNICATION_INSTRUCTIONS
from modules.infrastructure.llm_provider.llm_factory import get_llm, extract_text_content

class CommunicationWorker(BaseWorkerProtocol):
    """Independent Communication Worker module for Gmail messaging, drafts, and thread replies."""
    name = "CommunicationWorker"
    description = "Manages email communications, reading unread messages, sending emails, drafting, and replying via Gmail."
    instructions = COMMUNICATION_INSTRUCTIONS
    tools = communication_tools
    categories = ["email", "communication", "gmail", "CommunicationWorker"]

    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.0, llm_client: Optional[Any] = None):
        self._llm = llm_client or get_llm(model_name=model_name, temperature=temperature)
        self._agent = create_react_agent(self._llm, self.tools, prompt=self.instructions)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "Any email interactions, checking inboxes, drafting emails, replying to messages, or sending emails must be routed to CommunicationWorker."
        ]

    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Task: {description}"
        if context.get("working_memory"):
            prompt += f"\nAvailable Context: {context['working_memory']}"
        try:
            result = self._agent.invoke({"messages": [HumanMessage(content=prompt)]})
            messages = result.get("messages", [])
            last_msg = extract_text_content(messages[-1].content) if messages else "Email task executed."
            return {
                "status": "completed",
                "summary": last_msg,
                "data": {"communication_task_result": last_msg}
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": f"CommunicationWorker execution failed: {e}",
                "data": {},
                "error_message": str(e)
            }

if __name__ == "__main__":
    import sys
    task_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Check my latest unread emails"
    print(f"\n🚀 Running CommunicationWorker standalone...")
    print(f"Task: {task_desc}\n")
    worker = CommunicationWorker()
    output = worker.execute_task("standalone_comm_1", task_desc, {})
    print(f"Status : {output['status']}")
    print(f"Summary: {output['summary']}")
    if output.get("error_message"):
        print(f"Error  : {output['error_message']}")
