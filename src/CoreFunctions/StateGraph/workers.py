import os
import sys
import json
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from src.CoreFunctions.StateGraph.state import AgentState

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.CoreFunctions.LangGraph.available_tools import (
    system_control_tools, file_management_tools, system_info_tools,
    gmail_tools, calendar_tools, memory_tools, classroom_tools
)

# LLM for workers. Using Gemini for stability.
llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0)

# Local LLM for Memory and lightweight workers.
local_llm = ChatOllama(model="gemma4:e2b", temperature=0)

# Define prompts
SYSTEM_PROMPT_SYSTEM = "You are SystemWorker. You manage OS tasks, files, commands, and health metrics."
SYSTEM_PROMPT_GMAIL = "You are GmailWorker. You manage email fetching, searching, and sending."
SYSTEM_PROMPT_PRODUCTIVITY = "You are ProductivityWorker. You manage calendars, tasks, scheduling, and weather/time checks."
SYSTEM_PROMPT_MEMORY = "You are MemoryWorker. You save and retrieve long-term user preferences."
SYSTEM_PROMPT_CLASSROOM = "You are ClassroomWorker. You manage Google Classroom courses, assignments, announcements, and coursework details."

# Pre-compile the agents ONCE globally at load time
SYSTEM_AGENT = create_react_agent(llm, system_control_tools + file_management_tools + system_info_tools, prompt=SYSTEM_PROMPT_SYSTEM)
GMAIL_AGENT = create_react_agent(llm, gmail_tools, prompt=SYSTEM_PROMPT_GMAIL)
PRODUCTIVITY_AGENT = create_react_agent(llm, calendar_tools + system_info_tools, prompt=SYSTEM_PROMPT_PRODUCTIVITY)
MEMORY_AGENT = create_react_agent(local_llm, memory_tools, prompt=SYSTEM_PROMPT_MEMORY)
CLASSROOM_AGENT = create_react_agent(llm, classroom_tools, prompt=SYSTEM_PROMPT_CLASSROOM)

AGENT_MAP = {
    "SystemWorker": SYSTEM_AGENT,
    "GmailWorker": GMAIL_AGENT,
    "ProductivityWorker": PRODUCTIVITY_AGENT,
    "MemoryWorker": MEMORY_AGENT,
    "ClassroomWorker": CLASSROOM_AGENT
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
                        if msg.content:
                            thought = msg.content.strip()
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
