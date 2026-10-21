from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from modules.contracts.worker_contract import BaseWorkerProtocol
from modules.workers.research_worker.tools import tools as research_tools
from modules.workers.research_worker.prompts import RESEARCH_INSTRUCTIONS
from modules.infrastructure.llm_provider.llm_factory import get_llm, extract_text_content

class ResearchWorker(BaseWorkerProtocol):
    """Independent Research Worker module for deep and extreme web research."""
    name = "ResearchWorker"
    description = (
        "Conducts web and academic research across Extreme Research (multi-agent council mode), "
        "Deep Research (recursive web crawl and detailed reports), and quick web search."
    )
    instructions = RESEARCH_INSTRUCTIONS
    tools = research_tools
    categories = ["research", "web-search", "deep-research", "extreme-research", "ResearchWorker"]

    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.1, llm_client: Optional[Any] = None):
        self._llm = llm_client or get_llm(model_name=model_name, temperature=temperature)
        self._agent = create_react_agent(self._llm, self.tools, prompt=self.instructions)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "Any research inquiries, web lookups, market studies, technical investigations, literature reviews, or deep research requests must be routed to ResearchWorker."
        ]

    def execute_task(self, task_id: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Task: {description}"
        if context.get("working_memory"):
            prompt += f"\nAvailable Context: {context['working_memory']}"
        try:
            result = self._agent.invoke({"messages": [HumanMessage(content=prompt)]})
            messages = result.get("messages", [])
            last_msg = extract_text_content(messages[-1].content) if messages else "Research completed."
            return {
                "status": "completed",
                "summary": last_msg,
                "data": {"research_task_result": last_msg}
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": f"ResearchWorker execution failed: {e}",
                "data": {},
                "error_message": str(e)
            }

if __name__ == "__main__":
    import sys
    task_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Quick research on the latest Python 3.14 features"
    print(f"\n🚀 Running ResearchWorker standalone...")
    print(f"Task: {task_desc}\n")
    worker = ResearchWorker()
    output = worker.execute_task("standalone_research_1", task_desc, {})
    print(f"Status : {output['status']}")
    print(f"Summary: {output['summary']}")
    if output.get("error_message"):
        print(f"Error  : {output['error_message']}")
