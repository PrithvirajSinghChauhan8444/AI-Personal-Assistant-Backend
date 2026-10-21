from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.workers.youtube_worker.tools import tools as youtube_tools
from modules.workers.youtube_worker.prompts import YOUTUBE_INSTRUCTIONS
from modules.infrastructure.llm_provider.llm_factory import get_llm, extract_text_content

class YoutubeWorker(BaseWorkerProtocol):
    """Independent YouTube Worker module."""
    name = "YoutubeWorker"
    description = "Interacts with YouTube: fetches subscriptions, searches videos, transcribes videos for summaries, and tracks video states."
    instructions = YOUTUBE_INSTRUCTIONS
    tools = youtube_tools
    categories = ["youtube", "media", "information-retrieval", "YoutubeWorker"]

    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.0, llm_client: Optional[Any] = None):
        self._llm = llm_client or get_llm(model_name=model_name, temperature=temperature)
        self._agent = create_react_agent(self._llm, self.tools, prompt=self.instructions)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "Any requests related to YouTube (such as searching for videos, checking subscribed channel updates, transcribing or summarizing YouTube videos, or updating video viewed status) must be routed to YoutubeWorker."
        ]

    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Task: {description}"
        if context.get("working_memory"):
            prompt += f"\nAvailable Context: {context['working_memory']}"
        try:
            result = self._agent.invoke({"messages": [HumanMessage(content=prompt)]})
            messages = result.get("messages", [])
            last_msg = extract_text_content(messages[-1].content) if messages else "YouTube execution completed."
            return {
                "status": "completed",
                "summary": last_msg,
                "data": {"youtube_task_result": last_msg}
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": f"YoutubeWorker execution failed: {e}",
                "data": {},
                "error_message": str(e)
            }

if __name__ == "__main__":
    import sys
    task_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Search for recent Python tutorial videos"
    print(f"\n🚀 Running YoutubeWorker standalone...")
    print(f"Task: {task_desc}\n")
    worker = YoutubeWorker()
    output = worker.execute_task("standalone_yt_1", task_desc, {})
    print(f"Status : {output['status']}")
    print(f"Summary: {output['summary']}")
    if output.get("error_message"):
        print(f"Error  : {output['error_message']}")
