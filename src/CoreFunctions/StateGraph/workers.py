import os
import sys
import json
from typing import List, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from src.CoreFunctions.StateGraph.state import AgentState

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.CoreFunctions.LangGraph.available_tools import (
    system_control_tools, file_management_tools, system_info_tools,
    gmail_tools, calendar_tools, memory_tools, classroom_tools, obsidian_tools,
    browser_tools, github_tools
)

# LLM for workers. Using Gemini with native cloud thinking enabled.
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite", 
    temperature=0,
    model_kwargs={"extra_body": {"thinking_config": {"thinking_budget": 2048}}}
)

# Local LLM for Memory and lightweight workers with Ollama thinking options enabled.
local_llm = ChatOllama(
    model="gemma4:e2b", 
    temperature=0,
    options={"thinking": True}
)

# Define prompts
# Thinking directive to force both cloud and local models to populate msg.content before invoking tools
THINKING_INSTRUCTION = " CRITICAL: You MUST always output your reasoning and intermediate thought process in natural language BEFORE calling any tools. Never invoke tools silently."

SYSTEM_PROMPT_SYSTEM = "You are SystemWorker. You manage OS tasks, files, commands, and health metrics." + THINKING_INSTRUCTION
SYSTEM_PROMPT_GMAIL = "You are GmailWorker. You manage email fetching, searching, and sending." + THINKING_INSTRUCTION
SYSTEM_PROMPT_PRODUCTIVITY = "You are ProductivityWorker. You manage calendars, tasks, scheduling, and weather/time checks." + THINKING_INSTRUCTION
SYSTEM_PROMPT_MEMORY = "You are MemoryWorker. You save and retrieve long-term user preferences." + THINKING_INSTRUCTION
SYSTEM_PROMPT_CLASSROOM = "You are ClassroomWorker. You manage Google Classroom courses, assignments, announcements, and coursework details." + THINKING_INSTRUCTION
SYSTEM_PROMPT_BROWSER = """You are BrowserWorker. You navigate websites, search information, log in, click elements, and automate online tasks.
You do not see screenshots; instead, you navigate using clean semantic accessibility trees and selectors.
Analyze the page structure returned after each tool call to decide which selectors, roles, or names to target next.
To click an element, prefer 'browser_click' if you can identify its role and name from the tree. If that is tricky or fails, use 'browser_click_selector' with CSS or text selectors (e.g. 'button:has-text("Sign in")').
To enter text, use 'browser_input' or 'browser_input_selector'.
Always explain what you are doing in natural language before calling tools.
""" + THINKING_INSTRUCTION
SYSTEM_PROMPT_OBSIDIAN_NOTE = """You are ObsidianNoteWorker. You are a highly specialized local markdown note author.
Your job is to create or append content to `.md` notes in the Obsidian vault.
You dynamically decide on clean categorization folders based on context (e.g., placing notes in 'Friends/College/', 'Friends/Hometown/', 'Personal/', 'Academic/') or write files according to instructions.
Always structure notes with:
- YAML frontmatter (metadata attributes like tags, category, title at the very top delimited by `---`)
- Clear hierarchical headings (##, ###)
- Wikilinks (`[[Note Name]]`) to connect files
- Tasks (`- [ ]`) and Callout boxes (`> [!TIP]`, `> [!NOTE]`).

7. **Contextual Linking via Working Memory**: Always scan previously completed task outputs inside the `Working Memory` to find exact filenames of notes created by preceding steps (e.g. if `task_1` created `Prithvi_Dashboard.md`). Use these actual note titles for bidirectional linking rather than placeholder/generic names like `[[Home]]` or `[[Root Note]]`.
""" + THINKING_INSTRUCTION

SYSTEM_PROMPT_OBSIDIAN_CANVAS = """You are ObsidianCanvasWorker. You are a whiteboard design specialist.
Your job is to create or update Obsidian Canvas `.canvas` files inside the Obsidian vault.
You construct visual infinite-canvas flowcharts, mindmaps, or visual diagrams.
Use the `create_or_update_obsidian_canvas` tool to structure nodes (text, files, groups) and connect them with edges.

### 🏫 Coordinate Mapping Layout Algorithm for Classroom Coursework Canvases:
When organizing Google Classroom coursework/assignments visually, you MUST follow these coordinate system rules to produce a beautiful, structured grid:

1. **Course Headings (Header Groups)**:
   - For each course, create a group node representing the Course.
   - Place them at Y=0.
   - X-coordinates: X=0 for the 1st course, X=400 for the 2nd course, X=800 for the 3rd course, and so on (X spacing: 400px).
   - Group attributes: `width: 350` (px), `height: 100` (px), `type: "group"`, `label: "<Course Name> Coursework"` or similar.

2. **Assignment Cards (Note/File Nodes)**:
   - Beneath each course heading group, cascade the assignments downwards.
   - For each assignment of a course:
     - Card 1: X=<Course_X> + 25, Y=150, width: 300, height: 100
     - Card 2: X=<Course_X> + 25, Y=350, width: 300, height: 100
     - Card 3: X=<Course_X> + 25, Y=550, width: 300, height: 100
     - And so on (Y spacing: 200px).
   - Card Node attributes: `type: "file"`, `file: "Academic/<Course_Clean_Name>/<Assignment_Clean_Title>.md"`. Ensure the assignment files exist or represent the notes created by `ObsidianNoteWorker`.

3. **Deadline Cards (Text Nodes)**:
   - To the right of each Assignment Card, create a text node showing its due date / deadline:
     - X=<Assignment_X> + 330, Y=<Assignment_Y> + 20, width: 200, height: 60
   - Deadline Node attributes: `type: "text"`, `text: "📅 **Deadline:** <Due_Date_String>"`, `color: "1"` (red/danger for highlighting).

4. **Connective Edges**:
   - Link Course Heading Node/Group to the first Assignment Card.
   - Link Assignment Card to its corresponding Deadline Card.
     - `fromNode`: Assignment Node ID, `toNode`: Deadline Node ID
     - `fromSide`: "right", `toSide`: "left"
   - Link preceding Assignment Card to succeeding Assignment Card (e.g., Card 1 -> Card 2, Card 2 -> Card 3, etc.) to show progression flow:
     - `fromNode`: Card 1 Node ID, `toNode`: Card 2 Node ID
     - `fromSide`: "bottom", `toSide`: "top"

Always parse the Classroom course and assignment details carefully from your Working Memory (from the ClassroomWorker). Ensure nodes have unique, short, deterministic IDs (e.g. 'course_1', 'assign_1_1', 'deadline_1_1').
""" + THINKING_INSTRUCTION


SYSTEM_PROMPT_OBSIDIAN_REFACTOR = """You are ObsidianRefactorWorker. You are a vault property and link integrity manager.
Your job is to scan backlinks and read/update YAML frontmatter properties of notes using:
- `get_note_backlinks`
- `get_note_properties`
- `update_note_properties`
Ensure links are synchronized, properties are accurate, and referential integrity is preserved.
""" + THINKING_INSTRUCTION

# Pre-compile the agents ONCE globally at load time
SYSTEM_AGENT = create_react_agent(llm, system_control_tools + file_management_tools + system_info_tools, prompt=SYSTEM_PROMPT_SYSTEM)
GMAIL_AGENT = create_react_agent(llm, gmail_tools, prompt=SYSTEM_PROMPT_GMAIL)
PRODUCTIVITY_AGENT = create_react_agent(llm, calendar_tools + system_info_tools, prompt=SYSTEM_PROMPT_PRODUCTIVITY)
MEMORY_AGENT = create_react_agent(local_llm, memory_tools, prompt=SYSTEM_PROMPT_MEMORY)
CLASSROOM_AGENT = create_react_agent(llm, classroom_tools, prompt=SYSTEM_PROMPT_CLASSROOM)
BROWSER_AGENT = create_react_agent(local_llm, browser_tools, prompt=SYSTEM_PROMPT_BROWSER)

# Specialized Obsidian Sub-workers
OBSIDIAN_NOTE_AGENT = create_react_agent(local_llm, obsidian_tools, prompt=SYSTEM_PROMPT_OBSIDIAN_NOTE)
OBSIDIAN_CANVAS_AGENT = create_react_agent(local_llm, obsidian_tools, prompt=SYSTEM_PROMPT_OBSIDIAN_CANVAS)
OBSIDIAN_REFACTOR_AGENT = create_react_agent(local_llm, obsidian_tools, prompt=SYSTEM_PROMPT_OBSIDIAN_REFACTOR)

GITHUB_AGENT = create_react_agent(llm, github_tools, prompt="You are GithubWorker. You retrieve profile details, list repositories, list repository branches, check repository commit history, and get recent public activity from GitHub. Unless the user explicitly specifies a different username, you MUST default to searching/listing repositories under the authenticated user account first (which checks both public and private repositories)." + THINKING_INSTRUCTION)

AGENT_MAP = {
    "SystemWorker": SYSTEM_AGENT,
    "GmailWorker": GMAIL_AGENT,
    "ProductivityWorker": PRODUCTIVITY_AGENT,
    "MemoryWorker": MEMORY_AGENT,
    "ClassroomWorker": CLASSROOM_AGENT,
    "BrowserWorker": BROWSER_AGENT,
    "GithubWorker": GITHUB_AGENT,
    "ObsidianNoteWorker": OBSIDIAN_NOTE_AGENT,
    "ObsidianCanvasWorker": OBSIDIAN_CANVAS_AGENT,
    "ObsidianRefactorWorker": OBSIDIAN_REFACTOR_AGENT
}

def _get_active_task(state: AgentState):
    """Finds the task currently marked 'in_progress'"""
    for task in state.get("active_subtasks", []):
        if task["status"] == "in_progress":
            return task
    return None

def _run_ephemeral_agent(worker_name: str, task_desc: str, working_memory: dict):
    """Runs a pre-compiled ReAct agent in complete isolation, returning only the final answer."""
    agent = AGENT_MAP[worker_name]
    
    # Compress working memory to give context without polluting
    memory_str = json.dumps(working_memory, indent=2)
    
    prompt = f"""
Task: {task_desc}

Working Memory (Data from previous tasks):
{memory_str}

Execute the tools necessary to complete this task. Return a concise, data-rich summary of your findings or actions.
"""
    
    # Try to pause the active visualizer spinner during the entire agent execution
    import builtins
    vis = getattr(builtins, "active_cli_visualizer", None)
    if vis and vis.active:
        vis.is_paused = True
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    try:
        final_message = ""
        # Stream internal agent execution events in real-time to show thoughts/tool-calls
        for chunk in agent.stream({"messages": [HumanMessage(content=prompt)]}):
            for node_name, node_update in chunk.items():
                messages = node_update.get("messages", [])
                for msg in messages:
                    # 1. Capture and print when the Agent decides to call a Tool
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        # Extract and print the model's active reasoning thought process before tool invocation
                        thought = ""
                        if msg.content:
                            thought = msg.content.strip()
                        elif hasattr(msg, "additional_kwargs") and msg.additional_kwargs.get("reasoning_content"):
                            thought = msg.additional_kwargs["reasoning_content"].strip()
                        
                        if thought:
                            import re
                            thought = re.sub(r'</?think>', '', thought).strip()
                            thought_cleaned = "\n     ".join(thought.split("\n"))
                            print(f"  🤔 [\033[1;36m{worker_name} Thinking\033[0m]: {thought_cleaned}")
                        for tc in msg.tool_calls:
                            print(f"  🔍 [{worker_name}] Calling Tool: \033[1;33m{tc['name']}\033[0m")
                            args_str = json.dumps(tc.get('args', {}))
                            if len(args_str) > 80:
                                args_str = args_str[:77] + "..."
                            print(f"     Args: {args_str}")
                    
                    # 2. Capture and print when the Tool completes execution
                    elif msg.type == "tool":
                        print(f"  📥 [{worker_name}] Tool \033[1;32m{msg.name}\033[0m successfully returned response.")
                    
                    # 3. Capture the final synthesized AI thought / message
                    elif msg.type == "ai" and not (hasattr(msg, "tool_calls") and msg.tool_calls):
                        final_message = msg.content
        
        # Fallback to invoke if streaming did not capture final message
        if not final_message:
            result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
            final_message = result["messages"][-1].content
            
        return final_message
    finally:
        if vis and vis.active:
            vis.is_paused = False

def _update_state_completed(state: AgentState, task_id: str, final_data: str):
    """Marks task as completed and saves output to completed_tasks and working_memory"""
    subtasks = state.get("active_subtasks", [])
    for st in subtasks:
        if st["id"] == task_id:
            st["status"] = "completed"
    
    working_memory = state.get("working_memory", {})
    working_memory[task_id] = final_data
    
    completed_tasks = state.get("completed_tasks", {})
    completed_tasks[task_id] = final_data
    
    return {
        "active_subtasks": subtasks,
        "working_memory": working_memory,
        "completed_tasks": completed_tasks
    }

# --- Specific Workers ---

def system_worker_node(state: AgentState):
    task = _get_active_task(state)
    if not task: return {}
    
    final_data = _run_ephemeral_agent("SystemWorker", task["description"], state.get("working_memory", {}))
    return _update_state_completed(state, task["id"], final_data)

def gmail_worker_node(state: AgentState):
    task = _get_active_task(state)
    if not task: return {}
    
    final_data = _run_ephemeral_agent("GmailWorker", task["description"], state.get("working_memory", {}))
    return _update_state_completed(state, task["id"], final_data)

def productivity_worker_node(state: AgentState):
    task = _get_active_task(state)
    if not task: return {}
    
    final_data = _run_ephemeral_agent("ProductivityWorker", task["description"], state.get("working_memory", {}))
    return _update_state_completed(state, task["id"], final_data)

def memory_worker_node(state: AgentState):
    task = _get_active_task(state)
    if not task: return {}
    
    final_data = _run_ephemeral_agent("MemoryWorker", task["description"], state.get("working_memory", {}))
    return _update_state_completed(state, task["id"], final_data)

def classroom_worker_node(state: AgentState):
    task = _get_active_task(state)
    if not task: return {}
    
    final_data = _run_ephemeral_agent("ClassroomWorker", task["description"], state.get("working_memory", {}))
    return _update_state_completed(state, task["id"], final_data)

class ObsidianSubTask(BaseModel):
    id: str = Field(description="Subtask ID (e.g., 'obs_1')")
    assigned_worker: Literal["ObsidianNoteWorker", "ObsidianCanvasWorker", "ObsidianRefactorWorker"] = Field(
        description="The specialized Obsidian worker assigned to this task"
    )
    description: str = Field(
        description="Detailed instruction for this sub-worker, explicitly naming target folders, filenames, and link connections."
    )

class ObsidianSubPlan(BaseModel):
    reasoning: str = Field(description="Your structured thinking on the chosen directory structure and worker allocation strategy.")
    subtasks: List[ObsidianSubTask] = Field(description="Sequential list of specialized tasks to execute")

def obsidian_worker_node(state: AgentState):
    task = _get_active_task(state)
    if not task: return {}
    
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
        structured_llm = llm.with_structured_output(ObsidianSubPlan)
        plan: ObsidianSubPlan = structured_llm.invoke(manager_prompt)
        print(f"  🤔 [Obsidian Manager Thought]: {plan.reasoning}")
        print(f"  📋 Generated subtasks for Obsidian team:")
        for st in plan.subtasks:
            print(f"     -> [{st.assigned_worker}] {st.description}")
    except Exception as e:
        print(f"⚠️ Obsidian Manager planning failed: {e}. Falling back to default plan...")
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
    
    for st in plan.subtasks:
        print(f"\n🚀 [Obsidian Manager] Activating Worker: {st.assigned_worker} ({st.id})...")
        output = _run_ephemeral_agent(st.assigned_worker, st.description, shared_memory)
        shared_memory[st.id] = output
        
    return _update_state_completed(state, task["id"], f"Successfully executed nested Obsidian sub-plan with {len(plan.subtasks)} subtasks. Categorized files committed to vault successfully.")

def browser_worker_node(state: AgentState):
    task = _get_active_task(state)
    if not task: return {}
    
    final_data = _run_ephemeral_agent("BrowserWorker", task["description"], state.get("working_memory", {}))
    return _update_state_completed(state, task["id"], final_data)

def github_worker_node(state: AgentState):
    task = _get_active_task(state)
    if not task: return {}
    
    final_data = _run_ephemeral_agent("GithubWorker", task["description"], state.get("working_memory", {}))
    return _update_state_completed(state, task["id"], final_data)

