import os
import sys
import json
import re
from typing import List, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from src.CoreFunctions.StateGraph.state import AgentState

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.CoreFunctions.StateGraph.available_tools import (
    system_control_tools, file_management_tools, system_info_tools,
    gmail_tools, calendar_tools, memory_tools, classroom_tools, obsidian_tools,
    browser_tools, github_tools, misc_tools
)

# LLM for workers. Using Gemini/Gemma cloud models.
gemini_model_name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
llm_kwargs = {}
if "gemini" in gemini_model_name.lower():
    llm_kwargs["extra_body"] = {"thinking_config": {"thinking_budget": 2048}}

llm = ChatGoogleGenerativeAI(
    model=gemini_model_name, 
    temperature=0,
    model_kwargs=llm_kwargs
)

# Local LLM for Memory and lightweight workers with Ollama thinking options enabled.
local_llm = ChatOllama(
    model=os.environ.get("OLLAMA_MODEL", "gemma4:e4b"), 
    temperature=0,
    options={"thinking": True}
)

# Define prompts
# Thinking directive to force both cloud and local models to populate msg.content before invoking tools
TAGGING_INSTRUCTION = " CRITICAL FORMATTING RULE: You MUST always wrap critical information inside your text output in custom XML tags: wrap email addresses in <email>...</email>, URLs/links in <url>...</url>, passwords/credentials in <pass>...</pass>, and blocks of code in <code>...</code>. Do not wrap generic terms, only wrap actual values."
THINKING_INSTRUCTION = " CRITICAL: You MUST always output your reasoning and intermediate thought process in natural language BEFORE calling any tools. Never invoke tools silently." + TAGGING_INSTRUCTION
HUMAN_INTERVENTION_INSTRUCTION = """
### 🚨 HUMAN-IN-THE-LOOP (HITL) PROTOCOL:
You have access to the `request_human_intervention` tool. You MUST call this tool immediately to pause execution and request manual help from the human user in the following scenarios:
1. **Authentication, Login & 2FA**: If you require credentials, passwords, 2FA/OTP codes, API keys, OAuth approval, or if you hit CAPTCHAs, bot blocks, or verification screens.
2. **Permissions & System Prompts**: If you encounter 'Permission Denied' errors, a `sudo` password request, or system security blocks.
3. **Potentially Destructive Actions**: If you need to delete files, overwrite code, terminate critical processes, or make system-wide changes, and need confirmation.
4. **Roadblocks & Ambiguities**: If tools fail repeatedly, if you get stuck, or if the task instructions are ambiguous.
5. **User Manual Control**: If the user requests to perform an action manually or asks you to pause and wait.
Always explain the exact reason for pausing when calling the tool.
"""

SYSTEM_PROMPT_SYSTEM = "You are SystemWorker. You manage OS tasks, files, commands, and health metrics." + THINKING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION
SYSTEM_PROMPT_MISC = "You are MiscWorker. You handle miscellaneous tasks, general API integrations (such as YouTube Music API operations using external libraries like ytmusicapi or scripts), calculations, custom scripting, updating/creating system skills via `update_skill`, or general utility tasks that do not fit into other specialized workers." + THINKING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION
SYSTEM_PROMPT_GMAIL = "You are GmailWorker. You manage email fetching, searching, and sending." + THINKING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION
SYSTEM_PROMPT_PRODUCTIVITY = "You are ProductivityWorker. You manage calendars, tasks, scheduling, and weather/time checks." + THINKING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION
SYSTEM_PROMPT_MEMORY = "You are MemoryWorker. You save and retrieve long-term user preferences, and you also create or update specialized system skills/procedures using `update_skill` when requested." + THINKING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION
SYSTEM_PROMPT_CLASSROOM = "You are ClassroomWorker. You manage Google Classroom courses, assignments, announcements, and coursework details." + THINKING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION
SYSTEM_PROMPT_BROWSER_NAVIGATOR = "You are BrowserNavigator. Execute the browser actions (navigate, click, or input) requested in the task. CRITICAL RULE - INSPECT CURRENT PAGE FIRST: Before doing anything else (such as navigating or searching), you MUST always call `browser_read_current_page` first to inspect the current tab's active URL, page title, and elements. If the browser is already on the correct/target page, or if the page already shows the necessary controls or information, proceed directly with interaction or reading instead of navigating away. CRITICAL RULE - NO URL GUESSING: Never guess, fabricate, or make up URLs. If the exact URL is not provided in your task, you MUST use the `web_search` tool to look up the correct, official URL before navigating. CRITICAL RULE - ELEMENT PAGINATION: Interactive elements on pages are paginated. By default, only the first 30 elements are listed. If you need to click/fill an element that is not in the list (or if you want to inspect further down the page), you MUST call the tool again with a higher `offset` parameter (e.g., `offset=30`, `offset=60`, etc.) to view the next page of interactive elements. Once the action is successful, stop immediately and report the result. Do not repeat actions. If you encounter a CAPTCHA, bot detection, a 2FA prompt, or if the user asks to pause/perform an action manually, call `request_human_intervention` immediately. If you must wait for the user to perform an action, do not report completion until you have called `request_human_intervention` first to let them finish. If a website requires or works better with a sign-in, check if you are already logged in; if not, call `request_human_intervention` to let the user log in first. For reading textual content, you can use `browser_read_page_content` with mode='summary', mode='query', or mode='chunk'." + TAGGING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION
SYSTEM_PROMPT_BROWSER_READER = "You are BrowserReader. Read the page content, extract the requested information, and output it. CRITICAL RULE - INSPECT CURRENT PAGE FIRST: Before doing anything else (such as navigating or searching), you MUST always call `browser_read_current_page` first to inspect the current tab's active URL, page title, and elements. If the browser is already on the correct/target page, or if the page already shows the necessary controls or information, proceed directly with reading instead of navigating away. CRITICAL RULE - NO URL GUESSING: Never guess, fabricate, or make up URLs. If the exact URL is not provided in your task, you MUST use the `web_search` tool to look up the correct, official URL before navigating. CRITICAL RULE - ELEMENT PAGINATION: Interactive elements on pages are paginated. By default, only the first 30 elements are listed. If you need to click/fill/read an element that is not in the list (or if you want to inspect further down the page), you MUST call the tool again with a higher `offset` parameter (e.g., `offset=30`, `offset=60`, etc.) to view the next page of interactive elements. Once you have the information, stop immediately. If you encounter a CAPTCHA, bot detection, a 2FA prompt, or if the user asks to pause/perform an action manually, call `request_human_intervention` immediately. If you must wait for the user to perform an action, do not report completion until you have called `request_human_intervention` first to let them finish. If a website requires or works better with a sign-in, check if you are already logged in; if not, call `request_human_intervention` to let the user log in first. For reading webpage textual content, you MUST use `browser_read_page_content`. To avoid context limit issues, you can summarize long pages using `mode='summary'`, search/answer questions directly using `mode='query'`, or read raw text section by section using `mode='chunk'` (passing incrementing `chunk_index` values starting at 0). Never request the full page if it is extremely long; always use `summary` or `query` mode first." + TAGGING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION
SYSTEM_PROMPT_OBSIDIAN_NOTE = """You are ObsidianNoteWorker. You are a highly specialized local markdown note author.
Your job is to create or append content to `.md` notes in the Obsidian vault.
You dynamically decide on clean categorization folders based on context (e.g., placing notes in 'Friends/College/', 'Friends/Hometown/', 'Personal/', 'Academic/') or write files according to instructions.
Always structure notes with:
- YAML frontmatter (metadata attributes like tags, category, title at the very top delimited by `---`)
- Clear hierarchical headings (##, ###)
- Wikilinks (`[[Note Name]]`) to connect files
- Tasks (`- [ ]`) and Callout boxes (`> [!TIP]`, `> [!NOTE]`).

7. **Contextual Linking via Working Memory**: Always scan previously completed task outputs inside the `Working Memory` to find exact filenames of notes created by preceding steps (e.g. if `task_1` created `Prithvi_Dashboard.md`). Use these actual note titles for bidirectional linking rather than placeholder/generic names like `[[Home]]` or `[[Root Note]]`.
""" + THINKING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION

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
""" + THINKING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION


SYSTEM_PROMPT_OBSIDIAN_REFACTOR = """You are ObsidianRefactorWorker. You are a vault property and link integrity manager.
Your job is to scan backlinks and read/update YAML frontmatter properties of notes using:
- `get_note_backlinks`
- `get_note_properties`
- `update_note_properties`
Ensure links are synchronized, properties are accurate, and referential integrity is preserved.
""" + THINKING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION

# Pre-compile the agents ONCE globally at load time
SYSTEM_AGENT = create_react_agent(llm, system_control_tools + file_management_tools + system_info_tools, prompt=SYSTEM_PROMPT_SYSTEM)
GMAIL_AGENT = create_react_agent(llm, gmail_tools, prompt=SYSTEM_PROMPT_GMAIL)
PRODUCTIVITY_AGENT = create_react_agent(llm, calendar_tools + system_info_tools, prompt=SYSTEM_PROMPT_PRODUCTIVITY)
MEMORY_AGENT = create_react_agent(local_llm, memory_tools, prompt=SYSTEM_PROMPT_MEMORY)
CLASSROOM_AGENT = create_react_agent(llm, classroom_tools, prompt=SYSTEM_PROMPT_CLASSROOM)
BROWSER_NAVIGATOR_AGENT = create_react_agent(llm, browser_tools, prompt=SYSTEM_PROMPT_BROWSER_NAVIGATOR)
BROWSER_READER_AGENT = create_react_agent(llm, browser_tools, prompt=SYSTEM_PROMPT_BROWSER_READER)
BROWSER_AGENT = BROWSER_NAVIGATOR_AGENT  # Legacy fallback

# Specialized Obsidian Sub-workers
OBSIDIAN_NOTE_AGENT = create_react_agent(local_llm, obsidian_tools, prompt=SYSTEM_PROMPT_OBSIDIAN_NOTE)
OBSIDIAN_CANVAS_AGENT = create_react_agent(local_llm, obsidian_tools, prompt=SYSTEM_PROMPT_OBSIDIAN_CANVAS)
OBSIDIAN_REFACTOR_AGENT = create_react_agent(local_llm, obsidian_tools, prompt=SYSTEM_PROMPT_OBSIDIAN_REFACTOR)

GITHUB_AGENT = create_react_agent(llm, github_tools, prompt="You are GithubWorker. You retrieve profile details, list repositories, list repository branches, check repository commit history, retrieve recent public and private activity/events, inspect repository file contents and directories, and search code across repositories. You MUST always list and include private repositories by default when listing or searching repositories, unless the user explicitly specifies not to include them. Unless the user explicitly specifies a different username, you MUST default to searching/listing repositories/code under the authenticated user account first (which checks both public and private repositories)." + THINKING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION)
MISC_AGENT = create_react_agent(llm, misc_tools, prompt=SYSTEM_PROMPT_MISC)

AGENT_MAP = {
    "SystemWorker": SYSTEM_AGENT,
    "GmailWorker": GMAIL_AGENT,
    "ProductivityWorker": PRODUCTIVITY_AGENT,
    "MemoryWorker": MEMORY_AGENT,
    "ClassroomWorker": CLASSROOM_AGENT,
    "BrowserWorker": BROWSER_AGENT,
    "BrowserNavigator": BROWSER_NAVIGATOR_AGENT,
    "BrowserReader": BROWSER_READER_AGENT,
    "GithubWorker": GITHUB_AGENT,
    "ObsidianNoteWorker": OBSIDIAN_NOTE_AGENT,
    "ObsidianCanvasWorker": OBSIDIAN_CANVAS_AGENT,
    "MiscWorker": MISC_AGENT
}

def _get_active_task(state: AgentState, worker_name: str):
    """Finds the task currently marked 'in_progress' and assigned to the given worker"""
    for task in state.get("active_subtasks", []):
        if task["status"] == "in_progress" and task["assigned_worker"] == worker_name:
            return task
    return None

WORKER_CATEGORY_MAP = {
    "SystemWorker": ["system-management", "system-monitoring", "system-automation", "SystemWorker"],
    "GmailWorker": ["communication", "GmailWorker"],
    "ProductivityWorker": ["productivity", "ProductivityWorker"],
    "GithubWorker": ["development", "dev-utils", "GithubWorker"],
    "ClassroomWorker": ["academic", "education", "ClassroomWorker"],
    "BrowserWorker": ["browser", "information-retrieval", "BrowserWorker"],
    "BrowserNavigator": ["browser", "BrowserNavigator"],
    "BrowserReader": ["browser", "BrowserReader"],
    "ObsidianNoteWorker": ["obsidian", "knowledge-management", "ObsidianNoteWorker"],
    "ObsidianCanvasWorker": ["obsidian", "ObsidianCanvasWorker"],
    "ObsidianRefactorWorker": ["obsidian", "ObsidianRefactorWorker"],
    "MiscWorker": ["general", "misc", "MiscWorker"]
}

def _load_worker_skills(worker_name: str) -> str:
    """Dynamically loads and formats procedural skills matching the categories assigned to a worker using the skills index cache."""
    from src.CoreFunctions.vector_memory import _load_skills_data
    
    categories = WORKER_CATEGORY_MAP.get(worker_name, [worker_name])
    categories_lower = [cat.strip().lower() for cat in categories]
    
    skills_data = _load_skills_data()
    if not skills_data:
        return ""
        
    skills_content = []
    
    # Filter skills that match the worker's categories
    for skill in skills_data:
        skill_cat = skill.get("category", "").strip().lower()
        if skill_cat in categories_lower:
            skill_path = skill.get("path")
            if skill_path and os.path.exists(skill_path):
                try:
                    with open(skill_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                    name = skill.get("name", "")
                    desc = skill.get("description", "")
                    
                    content_clean = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL).strip()
                    if name:
                        header = f"## Skill: {name}"
                        if desc:
                            header += f" - {desc}"
                        content_clean = f"{header}\n{content_clean}"
                    skills_content.append(content_clean)
                except Exception:
                    pass
                    
    if not skills_content:
        return ""
    return "\n\n---\n\n".join(skills_content)

def _clean_working_memory_for_worker(working_memory: dict, depends_on: list = None) -> dict:
    """Cleans up the working memory dictionary to remove system-wide keys and optionally filter to direct task dependencies to prevent prompt context bloat."""
    cleaned = {}
    
    # 1. Retain user profile (general context)
    if "user_profile" in working_memory:
        cleaned["user_profile"] = working_memory["user_profile"]
        
    # 2. To save context, we only pass task outputs if explicitly defined in depends_on.
    # We do NOT pass previous_session_summary, active_skills, or skills_index.
    # We do NOT pass relevant_memories by default to avoid huge context bloat (planner should extract needed info into the task description).
    
    if depends_on is not None:
        for dep in depends_on:
            if dep in working_memory:
                cleaned[dep] = working_memory[dep]
    else:
        # Fallback if depends_on is None: Include all task keys but exclude system metadata keys
        system_keys = {"active_skills", "skills_index", "previous_session_summary", "user_profile", "relevant_memories", "fast_path_matched"}
        for k, v in working_memory.items():
            if k not in system_keys:
                cleaned[k] = v
                
    return cleaned

def _run_ephemeral_agent(worker_name: str, task_desc: str, working_memory: dict, depends_on: list = None):
    """Runs a pre-compiled ReAct agent in complete isolation, returning only the final answer."""
    from src.CoreFunctions.logger import log_worker_start, log_worker_thought, log_worker_tool_call, log_worker_tool_response, log_worker_end
    agent = AGENT_MAP[worker_name]
    
    # Compress working memory to give context without polluting, filtering out redundant system keys
    cleaned_memory = _clean_working_memory_for_worker(working_memory, depends_on)
    memory_str = json.dumps(cleaned_memory, indent=2)
    
    stable_guideline = (
        "IMPORTANT NOTE ON LARGE DATA:\n"
        "If any entry in the Working Memory contains a `\"__file_reference__\"`, the actual large data has "
        "been saved to that local file path to avoid context bloat. You can directly read the content of "
        "that file using your file-reading tools (like `read_file_tool` or running python/terminal commands), "
        "copy/move the file, or use the file path as an attachment/input for other tools."
    )
    
    skills_str = _load_worker_skills(worker_name)
    skills_section = ""
    if skills_str:
        skills_section = (
            f"\n\n### Specialized Skills for {worker_name}:\n"
            f"Use the following step-by-step procedures when resolving tasks in your domain:\n"
            f"{skills_str}"
        )
        
    volatile_inputs = f"""
### Operational Context (Volatile):
Task: {task_desc}

Working Memory (Data from previous tasks):
{memory_str}

Execute the tools necessary to complete this task. Return a concise, data-rich summary of your findings or actions.
"""
    prompt = f"{stable_guideline}{skills_section}\n\n{volatile_inputs}"
    
    # Log worker run start
    is_local = worker_name in ["MemoryWorker", "ObsidianNoteWorker", "ObsidianCanvasWorker", "ObsidianRefactorWorker"]
    model_name = os.environ.get("OLLAMA_MODEL", "gemma4:e4b") if is_local else os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    log_worker_start(worker_name, task_desc, model_name, prompt)

    # Try to pause the active visualizer spinner during the entire agent execution
    import builtins
    vis = getattr(builtins, "active_cli_visualizer", None)
    if vis and vis.active:
        vis.is_paused = True
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    from src.CoreFunctions.unified_memory import UnifiedMemory
    txn_id, token = UnifiedMemory().start_transaction()
    success = False
    try:
        last_ai_message = None
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
                            if isinstance(msg.content, str):
                                thought = msg.content.strip()
                            elif isinstance(msg.content, list):
                                text_parts = []
                                for item in msg.content:
                                    if isinstance(item, dict) and "text" in item:
                                        text_parts.append(item["text"])
                                    elif isinstance(item, str):
                                        text_parts.append(item)
                                thought = "".join(text_parts).strip()
                        elif hasattr(msg, "additional_kwargs") and msg.additional_kwargs.get("reasoning_content"):
                            thought = msg.additional_kwargs["reasoning_content"].strip()
                        
                        if thought:
                            import re
                            thought = re.sub(r'</?think>', '', thought).strip()
                            thought_cleaned = "\n     ".join(thought.split("\n"))
                            print(f"  🤔 [\033[1;36m{worker_name} Thinking\033[0m]: {thought_cleaned}")
                            log_worker_thought(worker_name, thought)
                        for tc in msg.tool_calls:
                            print(f"  🔍 [{worker_name}] Calling Tool: \033[1;33m{tc['name']}\033[0m")
                            args_str = json.dumps(tc.get('args', {}))
                            if len(args_str) > 80:
                                args_str = args_str[:77] + "..."
                            print(f"     Args: {args_str}")
                            log_worker_tool_call(worker_name, tc['name'], tc.get('args', {}))
                    
                    # 2. Capture and print when the Tool completes execution
                    elif msg.type == "tool":
                        print(f"  📥 [{worker_name}] Tool \033[1;32m{msg.name}\033[0m successfully returned response.")
                        log_worker_tool_response(worker_name, msg.name, getattr(msg, "content", ""))
                    
                    # 3. Keep track of the last AI message
                    if msg.type == "ai":
                        last_ai_message = msg
        
        # Capture final message content from the last AI message that doesn't have tool calls
        final_message = ""
        if last_ai_message and not (hasattr(last_ai_message, "tool_calls") and last_ai_message.tool_calls):
            content = last_ai_message.content
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                    elif isinstance(item, str):
                        text_parts.append(item)
                final_message = "".join(text_parts)
            else:
                final_message = str(content)
        
        # Fallback to invoke if streaming did not capture final message
        if not final_message:
            print(f"  ⚠️ [{worker_name}] Warning: Final message not captured via stream. Triggering fallback invoke...")
            result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
            content = result["messages"][-1].content
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                    elif isinstance(item, str):
                        text_parts.append(item)
                final_message = "".join(text_parts)
            else:
                final_message = str(content)
            
        log_worker_end(worker_name, final_message)
        success = True
        return final_message
    finally:
        if success:
            UnifiedMemory().commit_transaction(txn_id, token)
        else:
            UnifiedMemory().discard_transaction(txn_id, token)
        if vis and vis.active:
            vis.is_paused = False
 
async def _run_async_ephemeral_agent(worker_name: str, task_desc: str, working_memory: dict, depends_on: list = None):
    """Runs a pre-compiled async ReAct agent in complete isolation, returning only the final answer."""
    from src.CoreFunctions.logger import log_worker_start, log_worker_thought, log_worker_tool_call, log_worker_tool_response, log_worker_end
    agent = AGENT_MAP[worker_name]
    
    # Compress working memory to give context without polluting, filtering out redundant system keys
    cleaned_memory = _clean_working_memory_for_worker(working_memory, depends_on)
    memory_str = json.dumps(cleaned_memory, indent=2)
    
    stable_guideline = (
        "IMPORTANT NOTE ON LARGE DATA:\n"
        "If any entry in the Working Memory contains a `\"__file_reference__\"`, the actual large data has "
        "been saved to that local file path to avoid context bloat. You can directly read the content of "
        "that file using your file-reading tools (like `read_file_tool` or running python/terminal commands), "
        "copy/move the file, or use the file path as an attachment/input for other tools."
    )
    
    skills_str = _load_worker_skills(worker_name)
    skills_section = ""
    if skills_str:
        skills_section = (
            f"\n\n### Specialized Skills for {worker_name}:\n"
            f"Use the following step-by-step procedures when resolving tasks in your domain:\n"
            f"{skills_str}"
        )
        
    volatile_inputs = f"""
### Operational Context (Volatile):
Task: {task_desc}

Working Memory (Data from previous tasks):
{memory_str}

Execute the tools necessary to complete this task. Return a concise, data-rich summary of your findings or actions.
"""
    prompt = f"{stable_guideline}{skills_section}\n\n{volatile_inputs}"
    
    # Log worker run start
    is_local = worker_name in ["MemoryWorker", "ObsidianNoteWorker", "ObsidianCanvasWorker", "ObsidianRefactorWorker"]
    model_name = os.environ.get("OLLAMA_MODEL", "gemma4:e4b") if is_local else os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    log_worker_start(worker_name, task_desc, model_name, prompt)

    # Try to pause the active visualizer spinner during the entire agent execution
    import builtins
    vis = getattr(builtins, "active_cli_visualizer", None)
    if vis and vis.active:
        vis.is_paused = True
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    from src.CoreFunctions.unified_memory import UnifiedMemory
    txn_id, token = UnifiedMemory().start_transaction()
    success = False
    try:
        last_ai_message = None
        # Stream internal agent execution events in real-time to show thoughts/tool-calls
        async for chunk in agent.astream({"messages": [HumanMessage(content=prompt)]}):
            for node_name, node_update in chunk.items():
                messages = node_update.get("messages", [])
                for msg in messages:
                    # 1. Capture and print when the Agent decides to call a Tool
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        # Extract and print the model's active reasoning thought process before tool invocation
                        thought = ""
                        if msg.content:
                            if isinstance(msg.content, str):
                                thought = msg.content.strip()
                            elif isinstance(msg.content, list):
                                text_parts = []
                                for item in msg.content:
                                    if isinstance(item, dict) and "text" in item:
                                        text_parts.append(item["text"])
                                    elif isinstance(item, str):
                                        text_parts.append(item)
                                thought = "".join(text_parts).strip()
                        elif hasattr(msg, "additional_kwargs") and msg.additional_kwargs.get("reasoning_content"):
                            thought = msg.additional_kwargs["reasoning_content"].strip()
                        
                        if thought:
                            import re
                            thought = re.sub(r'</?think>', '', thought).strip()
                            thought_cleaned = "\n     ".join(thought.split("\n"))
                            print(f"  🤔 [\033[1;36m{worker_name} Thinking\033[0m]: {thought_cleaned}")
                            log_worker_thought(worker_name, thought)
                        for tc in msg.tool_calls:
                            print(f"  🔍 [{worker_name}] Calling Tool: \033[1;33m{tc['name']}\033[0m")
                            args_str = json.dumps(tc.get('args', {}))
                            if len(args_str) > 80:
                                args_str = args_str[:77] + "..."
                            print(f"     Args: {args_str}")
                            log_worker_tool_call(worker_name, tc['name'], tc.get('args', {}))
                    
                    # 2. Capture and print when the Tool completes execution
                    elif msg.type == "tool":
                        print(f"  📥 [{worker_name}] Tool \033[1;32m{msg.name}\033[0m successfully returned response.")
                        log_worker_tool_response(worker_name, msg.name, getattr(msg, "content", ""))
                    
                    # 3. Keep track of the last AI message
                    if msg.type == "ai":
                        last_ai_message = msg
        
        # Capture final message content from the last AI message that doesn't have tool calls
        final_message = ""
        if last_ai_message and not (hasattr(last_ai_message, "tool_calls") and last_ai_message.tool_calls):
            content = last_ai_message.content
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                    elif isinstance(item, str):
                        text_parts.append(item)
                final_message = "".join(text_parts)
            else:
                final_message = str(content)
        
        # Fallback to invoke if streaming did not capture final message
        if not final_message:
            print(f"  ⚠️ [{worker_name}] Warning: Final message not captured via stream. Triggering fallback invoke...")
            result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
            content = result["messages"][-1].content
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                    elif isinstance(item, str):
                        text_parts.append(item)
                final_message = "".join(text_parts)
            else:
                final_message = str(content)
            
        log_worker_end(worker_name, final_message)
        success = True
        return final_message
    finally:
        if success:
            UnifiedMemory().commit_transaction(txn_id, token)
        else:
            UnifiedMemory().discard_transaction(txn_id, token)
        if vis and vis.active:
            vis.is_paused = False

def _update_state_completed(state: AgentState, task_id: str, final_data: str):
    """Marks task as completed and saves output to completed_tasks and working_memory"""
    subtasks = state.get("active_subtasks", [])
    for st in subtasks:
        if st["id"] == task_id:
            st["status"] = "completed"
    
    working_memory = state.get("working_memory", {})
    
    # 1. Parse entities first to check if caching is needed
    try:
        from src.CoreFunctions.unified_memory import UnifiedMemory
        um = UnifiedMemory()
        
        # Default clean_summary
        clean_summary = final_data
        has_entities = False
        
        if isinstance(final_data, str):
            extracted = UnifiedMemory.extract_entities(final_data)
            clean_summary = extracted["summary"]
            # Check if there are any extracted entities (like urls, emails, passwords, code, shared_data, etc.)
            has_entities = bool(extracted.get("extracted_entities"))
            
        elif isinstance(final_data, dict):
            # If it's already a dictionary, check if it has extracted_entities populated
            has_entities = bool(final_data.get("extracted_entities"))
            clean_summary = final_data.get("summary", final_data)

        # Store in UnifiedMemory ONLY if it is enabled AND contains shareable entities
        if um.enabled:
            if has_entities:
                um.store_memory(task_id, final_data, sharable=True, persistent=True)
                print(f"  ⚡ [UnifiedMemory] Shareable entities found. Storing '{task_id}' in workspace cache.")
            else:
                print(f"  ℹ️ [UnifiedMemory] Skipping store of transient output for '{task_id}' (no shareable tags found).")
        
        # Update final_data to be clean_summary for the graph's working memory
        final_data = clean_summary
        
    except Exception as um_err:
        print(f"  ⚠️ [UnifiedMemory] Failed to evaluate/write output to cache: {um_err}")

    # 2. Offload large content to a file reference for the state graph to avoid context bloat
    is_large = False
    serialized_data = None
    file_ext = ".txt"
    
    if isinstance(final_data, str):
        if len(final_data) > 2000:
            is_large = True
            serialized_data = final_data
            file_ext = ".txt"
    elif isinstance(final_data, (dict, list)):
        try:
            serialized = json.dumps(final_data, indent=2)
            if len(serialized) > 2000:
                is_large = True
                serialized_data = serialized
                file_ext = ".json"
        except Exception:
            pass

    if is_large and serialized_data is not None:
        try:
            cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.session_cache"))
            os.makedirs(cache_dir, exist_ok=True)
            file_path = os.path.join(cache_dir, f"{task_id}{file_ext}")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(serialized_data)
            
            final_data = {
                "__file_reference__": file_path,
                "size_bytes": len(serialized_data),
                "preview": serialized_data[:200] + "... (truncated due to large size)"
            }
            print(f"  📂 [State Cache] Large output from {task_id} offloaded to: {file_path}")
        except Exception as cache_ex:
            print(f"  ⚠️ [State Cache] Failed to cache large output: {cache_ex}")
            
    working_memory[task_id] = final_data
    
    completed_tasks = state.get("completed_tasks", {})
    completed_tasks[task_id] = final_data
    
    return {
        "active_subtasks": subtasks,
        "working_memory": working_memory,
        "completed_tasks": completed_tasks
    }

# --- Specific Workers Helper ---

def _execute_worker_node(state: AgentState, worker_name: str):
    from src.CoreFunctions.logger import log_node_start, log_node_end, log_error
    log_node_start(worker_name, state)
    
    task = _get_active_task(state, worker_name)
    if not task:
        log_node_end(worker_name, {})
        return {}
    try:
        final_data = _run_ephemeral_agent(
            worker_name, 
            task["description"], 
            state.get("working_memory", {}),
            depends_on=task.get("depends_on", [])
        )
        output_state = _update_state_completed(state, task["id"], final_data)
        log_node_end(worker_name, output_state)
        return output_state
    except Exception as ex:
        print(f"  ❌ [{worker_name}] Task {task['id']} failed: {ex}")
        log_error(worker_name, str(ex))
        subtasks = state.get("active_subtasks", [])
        for st in subtasks:
            if st["id"] == task["id"]:
                st["status"] = "failed"
        error_logs = state.get("error_logs") or ""
        error_logs += f"\nWorker {worker_name} failed on task {task['id']}: {ex}"
        output_state = {
            "active_subtasks": subtasks,
            "error_logs": error_logs
        }
        log_node_end(worker_name, output_state)
        return output_state

# --- Specific Workers ---

def system_worker_node(state: AgentState):
    return _execute_worker_node(state, "SystemWorker")

def gmail_worker_node(state: AgentState):
    return _execute_worker_node(state, "GmailWorker")

def productivity_worker_node(state: AgentState):
    return _execute_worker_node(state, "ProductivityWorker")

def memory_worker_node(state: AgentState):
    return _execute_worker_node(state, "MemoryWorker")

def classroom_worker_node(state: AgentState):
    return _execute_worker_node(state, "ClassroomWorker")

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
    from src.CoreFunctions.logger import log_node_start, log_node_end, log_error, log_message
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
        import asyncio
        
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
    except Exception as ex:
        print(f"  ❌ [BrowserWorker] Task {task['id']} failed: {ex}")
        log_error("BrowserWorker", str(ex))
        subtasks = state.get("active_subtasks", [])
        for st in subtasks:
            if st["id"] == task["id"]:
                st["status"] = "failed"
        error_logs = state.get("error_logs") or ""
        error_logs += f"\nWorker BrowserWorker failed on task {task['id']}: {ex}"
        output_state = {
            "active_subtasks": subtasks,
            "error_logs": error_logs
        }
        log_node_end("BrowserWorker", output_state)
        return output_state

def github_worker_node(state: AgentState):
    return _execute_worker_node(state, "GithubWorker")

def misc_worker_node(state: AgentState):
    return _execute_worker_node(state, "MiscWorker")

