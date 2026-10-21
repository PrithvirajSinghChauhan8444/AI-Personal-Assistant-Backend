from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.workers.memory_worker.tools import tools as memory_tools
from modules.workers.memory_worker.prompts import MEMORY_INSTRUCTIONS
from modules.infrastructure.llm_provider.llm_factory import get_llm, extract_text_content

class MemoryWorker(BaseWorkerProtocol):
    """Independent Memory Worker module for user preferences and long-term memory."""
    name = "MemoryWorker"
    description = "Saves, recalls, updates, and searches long-term facts, preferences, chat history, and agent skills."
    instructions = MEMORY_INSTRUCTIONS
    tools = memory_tools
    categories = ["memory", "preferences", "skills", "history", "MemoryWorker"]

    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.0, llm_client: Optional[Any] = None):
        self._llm = llm_client or get_llm(model_name=model_name, temperature=temperature)
        self._agent = create_react_agent(self._llm, self.tools, prompt=self.instructions)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "Any requests to remember facts, recall saved user preferences, search past conversations, delete stored memories, or update learned skills must be routed to MemoryWorker."
        ]

    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Task: {description}"
        if context.get("working_memory"):
            prompt += f"\nAvailable Context: {context['working_memory']}"
        try:
            result = self._agent.invoke({"messages": [HumanMessage(content=prompt)]})
            messages = result.get("messages", [])
            last_msg = extract_text_content(messages[-1].content) if messages else "Memory operation completed."
            return {
                "status": "completed",
                "summary": last_msg,
                "data": {"memory_task_result": last_msg}
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": f"MemoryWorker execution failed: {e}",
                "data": {},
                "error_message": str(e)
            }

if __name__ == "__main__":
    import sys
    task_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Recall user preferences"
    print(f"\n🚀 Running MemoryWorker standalone...")
    print(f"Task: {task_desc}\n")
    worker = MemoryWorker()
    output = worker.execute_task("standalone_memory_1", task_desc, {})
    print(f"Status : {output['status']}")
    print(f"Summary: {output['summary']}")
    if output.get("error_message"):
        print(f"Error  : {output['error_message']}")
