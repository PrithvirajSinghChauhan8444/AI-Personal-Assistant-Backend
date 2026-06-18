import json
import asyncio
from typing import List, Literal
from pydantic import BaseModel, Field

from src.CoreFunctions.StateGraph.registry import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.state import AgentState
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_prompt import SYSTEM_PROMPT_BROWSER_NAVIGATOR, SYSTEM_PROMPT_BROWSER_READER
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_tools import browser_tools

class BrowserSubTask(BaseModel):
    id: str = Field(description="Subtask ID (e.g., 'br_1')")
    assigned_worker: Literal["BrowserNavigator", "BrowserReader"] = Field(
        description="The specialized Browser worker assigned to this task"
    )
    description: str = Field(
        description="Detailed instruction for this sub-worker. (e.g., 'Navigate to https://news.ycombinator.com', 'Locate the search input and type playwright')"
    )

class BrowserSubPlan(BaseModel):
    reasoning: str = Field(description="Structured thinking on how to break down the task and which worker to assign.")
    subtasks: List[BrowserSubTask] = Field(description="Sequential list of browser subtasks")

def browser_worker_node(state: AgentState):
    from src.CoreFunctions.logger import log_node_start, log_node_end, log_error, log_message
    from src.CoreFunctions.StateGraph.executor import llm, _run_async_ephemeral_agent, _get_active_task, _update_state_completed
    from src.CoreFunctions.tools import HumanInterventionAbortError, HumanInterventionReplanError

    log_node_start("BrowserWorker", state)
    
    task = _get_active_task(state, "BrowserWorker")
    if not task:
        log_node_end("BrowserWorker", {})
        return {}
    
    try:
        print(f"\n🧠 [Browser Manager] Decomposing high-level plan into specialized browser sub-tasks...")
        
        manager_prompt = f"""You are the Browser Manager. Your job is to orchestrate a team of specialized sub-workers:
- BrowserNavigator: Navigates websites, clicks interactive elements, and types inputs.
- BrowserReader: Reads page state, scrapes content, and extracts relevant information.

User Goal / Task: {task["description"]}

Working Memory Context:
{json.dumps(state.get("working_memory", {}), indent=2)}

Create a detailed sequential sub-plan to execute this goal.
"""
        try:
            log_message("BrowserWorker: Invoking model for structured subtask plan decomposition.")
            structured_llm = llm.with_structured_output(BrowserSubPlan)
            plan: BrowserSubPlan = structured_llm.invoke(manager_prompt)
            print(f"  🤔 [Browser Manager Thought]: {plan.reasoning}")
            print(f"  📋 Generated subtasks for Browser team:")
            for st in plan.subtasks:
                print(f"     -> [{st.assigned_worker}] {st.description}")
        except Exception as e:
            print(f"⚠️ Browser Manager planning failed: {e}. Falling back to default plan...")
            log_error("BrowserWorker", f"Manager planning failed: {e}")
            plan = BrowserSubPlan(
                reasoning="Fallback due to structured model error",
                subtasks=[
                    BrowserSubTask(
                        id="br_1", 
                        assigned_worker="BrowserNavigator", 
                        description=task["description"]
                    )
                ]
            )

        # Run the plan asynchronously
        async def run_plan():
            shared_memory = dict(state.get("working_memory", {}))
            for st in plan.subtasks:
                print(f"\n🚀 [Browser Manager] Activating Worker: {st.assigned_worker} ({st.id})...")
                output = await _run_async_ephemeral_agent(st.assigned_worker, st.description, shared_memory)
                shared_memory[st.id] = output
            return shared_memory

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            shared_memory = loop.run_until_complete(run_plan())
        else:
            shared_memory = loop.run_until_complete(run_plan())

        final_result = list(shared_memory.values())[-1] if shared_memory else "No actions performed"
        output_state = _update_state_completed(state, task["id"], final_result)
        log_node_end("BrowserWorker", output_state)
        return output_state
    except HumanInterventionAbortError as ex:
        print(f"  🛑 [BrowserWorker] Task aborted by user request.")
        subtasks = state.get("active_subtasks", [])
        for st in subtasks:
            if st["status"] in ["pending", "in_progress"]:
                st["status"] = "failed"
        working_memory = dict(state.get("working_memory", {}))
        working_memory["fast_path_matched"] = True
        output_state = {
            "active_subtasks": subtasks,
            "working_memory": working_memory,
            "final_response": "Execution aborted on-demand by the user.",
            "next_node": "OutputFinalizer"
        }
        log_node_end("BrowserWorker", output_state)
        return output_state
    except HumanInterventionReplanError as ex:
        print(f"  🔄 [BrowserWorker] Re-routing back to Task Router for re-planning.")
        subtasks = state.get("active_subtasks", [])
        for st in subtasks:
            if st["id"] == task["id"]:
                st["status"] = "failed"
        working_memory = dict(state.get("working_memory", {}))
        working_memory["replan_context"] = f"Task '{task['id']}' ({task['description']}) requested a re-plan. Roadblock reason: {ex.reason}. User feedback for re-planning: {ex.user_instruction}"
        output_state = {
            "active_subtasks": subtasks,
            "working_memory": working_memory,
            "next_node": "TaskRouter"
        }
        log_node_end("BrowserWorker", output_state)
        return output_state
    except Exception as ex:
        print(f"  ❌ [BrowserWorker] Task {task['id']} failed: {ex}")
        log_error("BrowserWorker", str(ex))
        subtasks = state.get("active_subtasks", [])
        for st in subtasks:
            if st["id"] == task["id"]:
                st["status"] = "failed"
        new_error = f"Worker BrowserWorker failed on task {task['id']}: {ex}"
        output_state = {
            "active_subtasks": subtasks,
            "error_logs": [new_error]
        }
        log_node_end("BrowserWorker", output_state)
        return output_state

@WorkerRegistry.register
class BrowserWorker(BaseWorker):
    name = "BrowserWorker"
    description = "Navigates websites, searches information, logs in, clicks elements, and automates online tasks."
    instructions = SYSTEM_PROMPT_BROWSER_NAVIGATOR
    tools = browser_tools
    categories = ["browser", "information-retrieval", "BrowserWorker"]
    
    @property
    def routing_rules(self) -> List[str]:
        return [
            "**Browser/Web Automation Workflow**:\n   - Web automation sessions (e.g. navigating to a website, searching, clicking, logging in, or playing media) MUST be kept as a single, combined subtask assigned to BrowserWorker.\n   - Do NOT break a single web session into multiple sequential BrowserWorker subtasks (e.g. step 1 navigate, step 2 search, step 3 click), because the browser page state and context are lost between different worker runs. Keep them combined in one subtask description (e.g., 'Navigate to music.youtube.com, search for j-pop, and play the first result')."
        ]

    def execute(self, state: AgentState) -> dict:
        return browser_worker_node(state)

@WorkerRegistry.register
class BrowserNavigator(BaseWorker):
    name = "BrowserNavigator"
    description = "Handles browser navigation and click/type interactions."
    instructions = SYSTEM_PROMPT_BROWSER_NAVIGATOR
    tools = browser_tools
    categories = ["browser", "BrowserNavigator"]
    is_graph_node = False

@WorkerRegistry.register
class BrowserReader(BaseWorker):
    name = "BrowserReader"
    description = "Reads and scrapes browser page content."
    instructions = SYSTEM_PROMPT_BROWSER_READER
    tools = browser_tools
    categories = ["browser", "BrowserReader"]
    is_graph_node = False
