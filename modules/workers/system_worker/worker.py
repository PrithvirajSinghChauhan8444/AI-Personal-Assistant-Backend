from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.workers.system_worker.tools import tools as system_tools
from modules.workers.system_worker.prompts import SYSTEM_INSTRUCTIONS
from modules.infrastructure.llm_provider.llm_factory import get_llm, extract_text_content

class SystemWorker(BaseWorkerProtocol):
    """Independent System Worker module for OS diagnostics, terminal commands, and file operations."""
    name = "SystemWorker"
    description = "Handles local system diagnostics, file reading/writing, OS environment execution, and media playback control (Spotify, YouTube Music, system audio)."
    instructions = SYSTEM_INSTRUCTIONS
    tools = system_tools
    categories = ["system", "files", "diagnostics", "media-playback", "spotify", "youtube-music"]

    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.0, llm_client: Optional[Any] = None):
        self._llm = llm_client or get_llm(model_name=model_name, temperature=temperature)
        self._agent = create_react_agent(self._llm, self.tools, prompt=self.instructions)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "Any file system reads or writes, CPU/RAM monitoring, or diagnostic health checks must be routed to SystemWorker.",
            "Any requests to control media playback, pause/play songs, skip tracks, check currently playing songs, or change volume on Spotify or YouTube Music should be routed to SystemWorker."
        ]

    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Task: {description}"
        if context.get("working_memory"):
            prompt += f"\nAvailable Context: {context['working_memory']}"
        try:
            result = self._agent.invoke({"messages": [HumanMessage(content=prompt)]})
            messages = result.get("messages", [])
            last_msg = extract_text_content(messages[-1].content) if messages else "Execution completed."
            return {
                "status": "completed",
                "summary": last_msg,
                "data": {"system_task_result": last_msg}
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": f"SystemWorker execution failed: {e}",
                "data": {},
                "error_message": str(e)
            }

if __name__ == "__main__":
    import sys
    task_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Check system health and resource metrics"
    print(f"\n🚀 Running SystemWorker standalone...")
    print(f"Task: {task_desc}\n")
    worker = SystemWorker()
    output = worker.execute_task("standalone_1", task_desc, {})
    print(f"Status : {output['status']}")
    print(f"Summary: {output['summary']}")
    if output.get("error_message"):
        print(f"Error  : {output['error_message']}")
