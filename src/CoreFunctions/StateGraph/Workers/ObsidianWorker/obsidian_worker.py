import json
from typing import List, Literal
from pydantic import BaseModel, Field

from src.CoreFunctions.StateGraph.registry import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.state import AgentState
from src.CoreFunctions.StateGraph.Workers.ObsidianWorker.obsidian_prompt import (
    SYSTEM_PROMPT_OBSIDIAN_NOTE,
    SYSTEM_PROMPT_OBSIDIAN_CANVAS,
    SYSTEM_PROMPT_OBSIDIAN_REFACTOR
)
from src.CoreFunctions.StateGraph.Workers.ObsidianWorker.obsidian_tools import obsidian_tools

class ObsidianSubTask(BaseModel):
    id: str = Field(description="Subtask ID (e.g., 'obs_1')")
    assigned_worker: Literal["ObsidianNoteWorker", "ObsidianCanvasWorker", "ObsidianRefactorWorker"] = Field(
        description="The specialized Obsidian worker assigned to this task"
    )
    description: str = Field(
        description="Detailed instruction for this sub-worker. (e.g., 'Create a new dashboard note with links to college friends.')"
    )

class ObsidianSubPlan(BaseModel):
    reasoning: str = Field(description="Your structured thinking on the chosen directory structure and worker allocation strategy.")
    subtasks: List[ObsidianSubTask] = Field(description="Sequential list of specialized tasks to execute")

def obsidian_worker_node(state: AgentState):
    from src.CoreFunctions.logger import log_node_start, log_node_end, log_error, log_message
    from src.CoreFunctions.StateGraph.executor import llm, _run_ephemeral_agent, _get_active_task, _update_state_completed
    from src.CoreFunctions.tools import HumanInterventionAbortError, HumanInterventionReplanError

    log_node_start("ObsidianWorker", state)
    
    task = _get_active_task(state, "ObsidianWorker")
    if not task:
        log_node_end("ObsidianWorker", {})
        return {}
    
    print(f"\n🧠 [Obsidian Manager] Decomposing high-level plan into specialized Obsidian sub-tasks...")
    
    # 1. Ask the Obsidian Manager to decompose the mega-task
    manager_prompt = f"""You are the Obsidian Manager. Your job is to orchestrate a team of specialized sub-workers:
- ObsidianNoteWorker: Creates or appends to markdown notes (.md), dynamically organizing them in appropriate folders (e.g. 'Friends/College_Friends/', 'Friends/Hometown_Friends/', 'Personal/', 'Academic/').
- ObsidianCanvasWorker: Creates/updates whiteboard infinite whiteboard flowcharts (.canvas).
- ObsidianRefactorWorker: Evaluates backlinks, properties, and links to keep notes synchronized.

User Goal / Task: {task["description"]}

Working Memory Context:
{json.dumps(state.get("working_memory", {}), indent=2)}

Create a detailed sequential sub-plan to execute this goal. 
RULES:
1. Dynamically structure categories into descriptive directories (e.g. 'Personal', 'Academic', 'Friends/College', 'Friends/Hometown') based on who the friends are in context.
2. Do not use generic file names like 'Home' or 'Root'. Establish clear custom note names (e.g., 'Prithvi_Dashboard.md').
3. Ensure every subsequent note created is explicitly commanded to contain a bidirectional wikilink back to the central hub Dashboard note.
4. **Classroom Coursework Canvas Visualizer Rule**: For classroom coursework canvas visualizer requests, first delegate `ObsidianNoteWorker` to create structured markdown notes for each fetched assignment/coursework under 'Academic/<Course_Clean_Name>/' containing full coursework descriptions, points, and deadlines. Then, delegate `ObsidianCanvasWorker` to build/update the Canvas (.canvas file) visualizing these courses, assignment files, deadline text cards, and connective edges using the strict Coordinate Mapping Layout Algorithm.
"""
    
    try:
        log_message("ObsidianWorker: Invoking model for structured subtask plan decomposition.")
        structured_llm = llm.with_structured_output(ObsidianSubPlan)
        plan: ObsidianSubPlan = structured_llm.invoke(manager_prompt)
        print(f"  🤔 [Obsidian Manager Thought]: {plan.reasoning}")
        print(f"  📋 Generated subtasks for Obsidian team:")
        for st in plan.subtasks:
            print(f"     -> [{st.assigned_worker}] {st.description}")
    except Exception as e:
        print(f"⚠️ Obsidian Manager planning failed: {e}. Falling back to default plan...")
        log_error("ObsidianWorker", f"Manager planning failed: {e}")
        plan = ObsidianSubPlan(
            reasoning="Fallback due to structured model error",
            subtasks=[
                ObsidianSubTask(
                    id="obs_1", 
                    assigned_worker="ObsidianNoteWorker", 
                    description=f"Create notes inside appropriate categorised subfolders: {task['description']}"
                )
            ]
        )

    # 2. Sequentially run each specialized subtask, updating the team's shared working memory
    shared_memory = dict(state.get("working_memory", {}))
    
    try:
        for st in plan.subtasks:
            print(f"\n🚀 [Obsidian Manager] Activating Worker: {st.assigned_worker} ({st.id})...")
            output = _run_ephemeral_agent(st.assigned_worker, st.description, shared_memory)
            shared_memory[st.id] = output
            
        output_state = _update_state_completed(state, task["id"], f"Successfully executed nested Obsidian sub-plan with {len(plan.subtasks)} subtasks. Categorized files committed to vault successfully.")
        log_node_end("ObsidianWorker", output_state)
        return output_state
    except HumanInterventionAbortError as ex:
        print(f"  🛑 [ObsidianWorker] Task aborted by user request.")
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
        log_node_end("ObsidianWorker", output_state)
        return output_state
    except HumanInterventionReplanError as ex:
        print(f"  🔄 [ObsidianWorker] Re-routing back to Task Router for re-planning.")
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
        log_node_end("ObsidianWorker", output_state)
        return output_state
    except Exception as ex:
        print(f"  ❌ [ObsidianWorker] nested sub-plan execution failed: {ex}")
        log_error("ObsidianWorker", str(ex))
        subtasks = state.get("active_subtasks", [])
        for st in subtasks:
            if st["id"] == task["id"]:
                st["status"] = "failed"
        error_logs = state.get("error_logs") or ""
        error_logs += f"\nWorker ObsidianWorker failed on subtask execution: {ex}"
        output_state = {
            "active_subtasks": subtasks,
            "error_logs": error_logs
        }
        log_node_end("ObsidianWorker", output_state)
        return output_state

@WorkerRegistry.register
class ObsidianWorker(BaseWorker):
    name = "ObsidianWorker"
    description = "Manages Obsidian notes, canvases, and property refactoring."
    instructions = ""
    tools = []
    categories = ["obsidian", "ObsidianWorker"]
    
    def execute(self, state: AgentState) -> dict:
        return obsidian_worker_node(state)

@WorkerRegistry.register
class ObsidianNoteWorker(BaseWorker):
    name = "ObsidianNoteWorker"
    description = "Creates or appends content to markdown notes."
    instructions = SYSTEM_PROMPT_OBSIDIAN_NOTE
    tools = obsidian_tools
    categories = ["obsidian", "knowledge-management", "ObsidianNoteWorker"]
    use_local_llm = True
    is_graph_node = False

@WorkerRegistry.register
class ObsidianCanvasWorker(BaseWorker):
    name = "ObsidianCanvasWorker"
    description = "Creates or updates whiteboard canvas diagrams."
    instructions = SYSTEM_PROMPT_OBSIDIAN_CANVAS
    tools = obsidian_tools
    categories = ["obsidian", "ObsidianCanvasWorker"]
    use_local_llm = True
    is_graph_node = False

@WorkerRegistry.register
class ObsidianRefactorWorker(BaseWorker):
    name = "ObsidianRefactorWorker"
    description = "Manages Obsidian properties, links, and backlinks."
    instructions = SYSTEM_PROMPT_OBSIDIAN_REFACTOR
    tools = obsidian_tools
    categories = ["obsidian", "ObsidianRefactorWorker"]
    use_local_llm = True
    is_graph_node = False
