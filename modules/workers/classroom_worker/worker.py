from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.workers.classroom_worker.tools import tools as classroom_tools
from modules.workers.classroom_worker.prompts import CLASSROOM_INSTRUCTIONS
from modules.infrastructure.llm_provider.llm_factory import get_llm, extract_text_content

class ClassroomWorker(BaseWorkerProtocol):
    """Independent Google Classroom Worker module."""
    name = "ClassroomWorker"
    description = "Manages Google Classroom courses, coursework, assignments, materials, and announcements."
    instructions = CLASSROOM_INSTRUCTIONS
    tools = classroom_tools
    categories = ["academic", "education", "classroom", "ClassroomWorker"]

    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.0, llm_client: Optional[Any] = None):
        self._llm = llm_client or get_llm(model_name=model_name, temperature=temperature)
        self._agent = create_react_agent(self._llm, self.tools, prompt=self.instructions)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "Any tasks involving Google Classroom, checking coursework, fetching classroom assignments or announcements, downloading class materials, or submitting homework must be routed to ClassroomWorker."
        ]

    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Task: {description}"
        if context.get("working_memory"):
            prompt += f"\nAvailable Context: {context['working_memory']}"
        try:
            result = self._agent.invoke({"messages": [HumanMessage(content=prompt)]})
            messages = result.get("messages", [])
            last_msg = extract_text_content(messages[-1].content) if messages else "Classroom execution completed."
            return {
                "status": "completed",
                "summary": last_msg,
                "data": {"classroom_task_result": last_msg}
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": f"ClassroomWorker execution failed: {e}",
                "data": {},
                "error_message": str(e)
            }

if __name__ == "__main__":
    import sys
    task_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "List my Google Classroom courses"
    print(f"\n🚀 Running ClassroomWorker standalone...")
    print(f"Task: {task_desc}\n")
    worker = ClassroomWorker()
    output = worker.execute_task("standalone_classroom_1", task_desc, {})
    print(f"Status : {output['status']}")
    print(f"Summary: {output['summary']}")
    if output.get("error_message"):
        print(f"Error  : {output['error_message']}")
