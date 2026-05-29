import os
import sys
import json
from typing import List, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Fallback to Gemini for robust structured output to avoid small model issues
from langchain_google_genai import ChatGoogleGenerativeAI
from src.CoreFunctions.StateGraph.state import AgentState

class SubTaskModel(BaseModel):
    id: str = Field(description="A unique identifier for the subtask, e.g., 'task_1'")
    description: str = Field(description="Clear instructions for the worker")
    assigned_worker: Literal["SystemWorker", "GmailWorker", "ProductivityWorker", "MemoryWorker", "ClassroomWorker"] = Field(
        description="The worker assigned to this task"
    )

class TaskPlan(BaseModel):
    subtasks: List[SubTaskModel] = Field(description="List of subtasks to execute in sequence")

ROUTER_PROMPT = """
You are the Task Router. Your job is to decompose the user's mega-prompt into isolated sub-tasks.
Available workers:
- GmailWorker: Reads, searches, and sends emails.
- ClassroomWorker: Manages Google Classroom courses, coursework, assignments, and announcements.
- ProductivityWorker: Calendar events, Google Tasks, Weather.
- MemoryWorker: Long-term memory storage and retrieval.
- SystemWorker: OS terminal commands, file management, scripts, system health.

RULES:
1. Break down the request into the smallest logical steps.
2. Assign each step to the correct worker.
3. Determine the sequential order of tasks.
"""

def task_router_node(state: AgentState):
    print("\n[Node: Task Router] Analyzing request...")
    primary_goal = state.get("primary_goal", "")
    working_memory = state.get("working_memory", {}) or {}
    chat_history = state.get("chat_history", []) or []
    
    user_profile = working_memory.get("user_profile", {})
    relevant_memories = working_memory.get("relevant_memories", [])
    
    # 1. Build conversational history
    history_str = ""
    if chat_history:
        history_str = "Conversation History:\n"
        for msg in chat_history:
            history_str += f"- {msg['role'].capitalize()}: {msg['content']}\n"
            
    # 2. Build user context profile
    context_str = ""
    if user_profile:
        context_str += f"User Profile Details: {json.dumps(user_profile)}\n"
    if relevant_memories:
        context_str += "Relevant Stored Memories / Past Facts:\n"
        for mem in relevant_memories:
            context_str += f"- {mem}\n"
            
    input_content = f"User Request: {primary_goal}\n"
    if context_str:
        input_content = f"Injected Context:\n{context_str}\n\n" + input_content
    if history_str:
        input_content = history_str + "\n" + input_content
    
    # Use a robust model for structured JSON parsing
    llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0)
    structured_llm = llm.with_structured_output(TaskPlan)
    
    plan: TaskPlan = structured_llm.invoke([
        SystemMessage(content=ROUTER_PROMPT),
        HumanMessage(content=input_content)
    ])
    
    active_subtasks = []
    for st in plan.subtasks:
        active_subtasks.append({
            "id": st.id,
            "description": st.description,
            "assigned_worker": st.assigned_worker,
            "status": "pending"
        })
        print(f"  -> Created Subtask: {st.id} ({st.assigned_worker})")
        
    return {
        "active_subtasks": active_subtasks,
        "working_memory": working_memory,
        "completed_tasks": {}
    }

