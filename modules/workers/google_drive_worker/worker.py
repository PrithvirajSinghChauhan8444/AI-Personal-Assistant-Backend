from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.workers.google_drive_worker.tools import tools as drive_tools
from modules.workers.google_drive_worker.prompts import GOOGLE_DRIVE_INSTRUCTIONS
from modules.infrastructure.llm_provider.llm_factory import get_llm, extract_text_content

class GoogleDriveWorker(BaseWorkerProtocol):
    """Independent Google Drive Worker module."""
    name = "GoogleDriveWorker"
    description = "Manages files on Google Drive (list, search, download, upload, create folder, delete)."
    instructions = GOOGLE_DRIVE_INSTRUCTIONS
    tools = drive_tools
    categories = ["cloud-storage", "drive", "files", "GoogleDriveWorker"]

    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.0, llm_client: Optional[Any] = None):
        self._llm = llm_client or get_llm(model_name=model_name, temperature=temperature)
        self._agent = create_react_agent(self._llm, self.tools, prompt=self.instructions)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "Any tasks involving Google Drive, uploading files to the cloud, downloading Drive documents, managing cloud folders, or searching Google Drive files must be routed to GoogleDriveWorker."
        ]

    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Task: {description}"
        if context.get("working_memory"):
            prompt += f"\nAvailable Context: {context['working_memory']}"
        try:
            result = self._agent.invoke({"messages": [HumanMessage(content=prompt)]})
            messages = result.get("messages", [])
            last_msg = extract_text_content(messages[-1].content) if messages else "Google Drive execution completed."
            return {
                "status": "completed",
                "summary": last_msg,
                "data": {"drive_task_result": last_msg}
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": f"GoogleDriveWorker execution failed: {e}",
                "data": {},
                "error_message": str(e)
            }

if __name__ == "__main__":
    import sys
    task_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "List my Google Drive files"
    print(f"\n🚀 Running GoogleDriveWorker standalone...")
    print(f"Task: {task_desc}\n")
    worker = GoogleDriveWorker()
    output = worker.execute_task("standalone_drive_1", task_desc, {})
    print(f"Status : {output['status']}")
    print(f"Summary: {output['summary']}")
    if output.get("error_message"):
        print(f"Error  : {output['error_message']}")
