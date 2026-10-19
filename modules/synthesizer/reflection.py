from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from modules.contracts.state_contract import AgentState
from modules.infrastructure.llm_provider.llm_factory import get_llm, extract_text_content
from modules.infrastructure.observability.telemetry import get_module_tracer

tracer = get_module_tracer("reflection")

class ReflectionEngine:
    """Independent Reflection & Passive Learning Module.
    Extracts durable user facts from completed turn exchanges.
    """
    def __init__(self, model_name: str = "gemini-3.1-flash-lite", llm_client: Optional[Any] = None):
        self.model_name = model_name
        self._llm = llm_client or get_llm(model_name=self.model_name, temperature=0.0)

    def extract_facts(self, user_goal: str, final_response: str) -> List[str]:
        with tracer.start_as_current_span("reflection.extract_facts") as span:
            span.set_attribute("reflection.user_goal", user_goal)
            prompt = """Analyze this assistant turn and extract any explicit durable user preferences, personal profile facts, or habits mentioned.
Return only facts as bullet points. If no new personal preferences or persistent facts were stated, return 'NONE'."""
            turn_text = f"User: {user_goal}\nAssistant: {final_response}"
            try:
                resp = self._llm.invoke([
                    SystemMessage(content=prompt),
                    HumanMessage(content=turn_text)
                ])
                text = extract_text_content(resp)
                if "NONE" in text.upper():
                    span.set_attribute("reflection.facts_count", 0)
                    return []
                facts = [line.strip("- ").strip() for line in text.split("\n") if line.strip().startswith("-")]
                span.set_attribute("reflection.facts_count", len(facts))
                return facts
            except Exception as e:
                span.record_exception(e)
                return []


    def as_node(self, state: AgentState) -> Dict[str, Any]:
        goal = state.get("primary_goal", "")
        final_resp = state.get("final_response", "")
        facts = self.extract_facts(goal, final_resp)
        return {"working_memory": {"extracted_reflection_facts": facts}}
