from typing import List, Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from modules.contracts.task_contract import TaskPlan, SubTaskModel, WorkerCapability
from modules.contracts.state_contract import AgentState, SubTask
from modules.task_router.prompt_templates import build_task_router_prompt
from modules.infrastructure.llm_provider.llm_factory import get_llm
from modules.infrastructure.observability.telemetry import get_module_tracer

tracer = get_module_tracer("task_router")

class TaskRouter:
    """Independent Intent Decomposition Module.
    Takes user goal + worker capabilities -> produces structured TaskPlan DAG.
    """
    def __init__(self, model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.1, llm_client: Optional[Any] = None):
        self.model_name = model_name
        self.temperature = temperature
        self._llm = llm_client or get_llm(model_name=self.model_name, temperature=self.temperature)

    def route(self, goal: str, available_workers: List[WorkerCapability], context: Optional[Dict[str, Any]] = None) -> TaskPlan:
        """Decomposes goal into structured TaskPlan DAG."""
        with tracer.start_as_current_span("task_router.route") as span:
            span.set_attribute("task_router.goal", goal)
            span.set_attribute("task_router.model", self.model_name)
            span.set_attribute("task_router.available_workers", [w.name for w in available_workers])

            sys_prompt = build_task_router_prompt(available_workers)
            user_prompt = f"Decompose this request:\n{goal}"
            if context:
                user_prompt += f"\nContext:\n{context}"

            structured_llm = self._llm.with_structured_output(TaskPlan)
            try:
                plan = structured_llm.invoke([
                    SystemMessage(content=sys_prompt),
                    HumanMessage(content=user_prompt)
                ])
                span.set_attribute("task_router.subtasks_count", len(plan.subtasks))
                span.set_attribute("task_router.status", "success")
                return plan
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("task_router.status", "fallback")
                # Do not mask quota or rate limit errors; fail fast so user is notified
                err_lower = str(e).lower()
                if any(k in err_lower for k in ["429", "resourceexhausted", "quota", "rate limit", "ratelimit", "too many requests"]):
                    raise e
                # Fallback single-task plan for parse or syntax errors
                fallback_worker = available_workers[0].name if available_workers else "SystemWorker"
                return TaskPlan(
                    primary_goal=goal,
                    subtasks=[
                        SubTaskModel(
                            id="task_1",
                            description=goal,
                            assigned_worker=fallback_worker,
                            depends_on=[],
                            confidence_score=0.5,
                            confidence_reason=f"Fallback due to decomposition error: {str(e)}"
                        )
                    ]
                )


    def as_node(self, state: AgentState, available_workers: List[WorkerCapability]) -> Dict[str, Any]:
        """LangGraph node compatible function."""
        goal = state.get("primary_goal", "")
        context = state.get("working_memory", {})
        plan = self.route(goal, available_workers, context)
        
        active_subtasks: List[SubTask] = []
        for st in plan.subtasks:
            active_subtasks.append({
                "id": st.id,
                "description": st.description,
                "assigned_worker": st.assigned_worker,
                "status": "pending",
                "depends_on": st.depends_on,
                "confidence_score": st.confidence_score,
                "confidence_reason": st.confidence_reason,
                "entity_reference": st.entity_reference
            })
            
        return {"active_subtasks": active_subtasks}
