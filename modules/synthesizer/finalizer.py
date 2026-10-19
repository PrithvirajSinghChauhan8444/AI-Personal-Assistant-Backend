from typing import Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from modules.contracts.state_contract import AgentState
from modules.infrastructure.llm_provider.llm_factory import get_llm

class OutputSynthesizer:
    """Independent Response Synthesis Module.
    Takes primary goal + completed task results -> produces coherent user-facing answer.
    """
    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.3, llm_client: Optional[Any] = None):
        self.model_name = model_name
        self.temperature = temperature
        self._llm = llm_client or get_llm(model_name=self.model_name, temperature=self.temperature)

    def synthesize(self, goal: str, completed_tasks: Dict[str, Any], working_memory: Optional[Dict[str, Any]] = None) -> str:
        if not completed_tasks:
            return "I completed your request, but no task updates were recorded."

        task_summaries = []
        for tid, tinfo in completed_tasks.items():
            worker = tinfo.get("worker", "Worker")
            desc = tinfo.get("description", tid)
            summary = tinfo.get("summary", "Done")
            task_summaries.append(f"- **{worker}** ({desc}): {summary}")
        tasks_text = "\n".join(task_summaries)

        sys_prompt = """You are the personal assistant output synthesizer.
Synthesize the executed task outputs into a direct, friendly, and complete final response for the user.
Highlight outcomes, specific results, and any relevant paths or data. Keep it clean and well-structured."""

        user_content = f"User Request: {goal}\n\nTask Outputs:\n{tasks_text}"
        try:
            resp = self._llm.invoke([
                SystemMessage(content=sys_prompt),
                HumanMessage(content=user_content)
            ])
            return resp.content if hasattr(resp, "content") else str(resp)
        except Exception as e:
            return f"Summary of results for '{goal}':\n\n{tasks_text}"

    def as_node(self, state: AgentState) -> Dict[str, Any]:
        goal = state.get("primary_goal", "")
        completed_tasks = state.get("completed_tasks", {}) or {}
        working_memory = state.get("working_memory", {}) or {}

        # If fast path already resolved the response
        if "fast_path_response" in working_memory:
            return {"final_response": working_memory["fast_path_response"]}

        final_resp = self.synthesize(goal, completed_tasks, working_memory)
        return {"final_response": final_resp}
