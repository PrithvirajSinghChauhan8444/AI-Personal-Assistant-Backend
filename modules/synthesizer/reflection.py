from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from modules.contracts.state_contract import AgentState
from modules.infrastructure.llm_provider.llm_factory import get_llm

class ReflectionEngine:
    """Independent Reflection & Passive Learning Module.
    Extracts durable user facts from completed turn exchanges.
    """
    def __init__(self, model_name: str = "gemini-3.1-flash-lite", llm_client: Optional[Any] = None):
        self.model_name = model_name
        self._llm = llm_client or get_llm(model_name=self.model_name, temperature=0.0)

    def extract_facts(self, user_goal: str, final_response: str) -> List[str]:
        prompt = """Analyze this assistant turn and extract any explicit durable user preferences, personal profile facts, or habits mentioned.
Return only facts as bullet points. If no new personal preferences or persistent facts were stated, return 'NONE'."""
        turn_text = f"User: {user_goal}\nAssistant: {final_response}"
        try:
            resp = self._llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=turn_text)
            ])
            text = resp.content if hasattr(resp, "content") else str(resp)
            if "NONE" in text.upper():
                return []
            return [line.strip("- ").strip() for line in text.split("\n") if line.strip().startswith("-")]
        except Exception:
            return []

    def as_node(self, state: AgentState) -> Dict[str, Any]:
        goal = state.get("primary_goal", "")
        final_resp = state.get("final_response", "")
        facts = self.extract_facts(goal, final_resp)
        return {"working_memory": {"extracted_reflection_facts": facts}}
