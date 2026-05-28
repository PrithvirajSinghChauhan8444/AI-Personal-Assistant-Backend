import os
import sys
import json
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from src.CoreFunctions.StateGraph.state import AgentState

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.CoreFunctions.LangGraph.available_tools import (
    system_control_tools, file_management_tools, system_info_tools,
    gmail_tools, calendar_tools, memory_tools
)

# LLM for workers. Using Gemini for stability.
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)

def _get_active_task(state: AgentState):
    """Finds the task currently marked 'in_progress'"""
    for task in state.get("active_subtasks", []):
        if task["status"] == "in_progress":
            return task
    return None

def _run_ephemeral_agent(worker_name: str, tools: list, system_prompt: str, task_desc: str, working_memory: dict):
    """Runs a ReAct agent in complete isolation, returning only the final answer."""
    agent = create_react_agent(llm, tools, prompt=system_prompt)
    
    # Compress working memory to give context without polluting
    memory_str = json.dumps(working_memory, indent=2)
    
    prompt = f"""
Task: {task_desc}

Working Memory (Data from previous tasks):
{memory_str}

Execute the tools necessary to complete this task. Return a concise, data-rich summary of your findings or actions.
"""
    result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
    final_message = result["messages"][-1].content
    return final_message

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
    
    tools = system_control_tools + file_management_tools + system_info_tools
    sys_prompt = "You are SystemWorker. You manage OS tasks, files, commands, and health metrics."
    
    final_data = _run_ephemeral_agent("SystemWorker", tools, sys_prompt, task["description"], state.get("working_memory", {}))
    return _update_state_completed(state, task["id"], final_data)

def gmail_worker_node(state: AgentState):
    task = _get_active_task(state)
    if not task: return {}
    
    tools = gmail_tools
    sys_prompt = "You are GmailWorker. You manage email fetching, searching, and sending."
    
    final_data = _run_ephemeral_agent("GmailWorker", tools, sys_prompt, task["description"], state.get("working_memory", {}))
    return _update_state_completed(state, task["id"], final_data)

def productivity_worker_node(state: AgentState):
    task = _get_active_task(state)
    if not task: return {}
    
    tools = calendar_tools + system_info_tools # Needs weather and time
    sys_prompt = "You are ProductivityWorker. You manage calendars, tasks, and scheduling."
    
    final_data = _run_ephemeral_agent("ProductivityWorker", tools, sys_prompt, task["description"], state.get("working_memory", {}))
    return _update_state_completed(state, task["id"], final_data)

def memory_worker_node(state: AgentState):
    task = _get_active_task(state)
    if not task: return {}
    
    tools = memory_tools
    sys_prompt = "You are MemoryWorker. You save and retrieve long-term user preferences."
    
    final_data = _run_ephemeral_agent("MemoryWorker", tools, sys_prompt, task["description"], state.get("working_memory", {}))
    return _update_state_completed(state, task["id"], final_data)
