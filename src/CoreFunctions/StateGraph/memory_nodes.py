import os
import sys
import json
from typing import Dict, List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.CoreFunctions.memory import store_memory, fetch_memory
from src.CoreFunctions.vector_memory import store_vector, search_vector
from src.CoreFunctions.StateGraph.state import AgentState

# Pydantic Model for Structured Reflection
class MemoryReflection(BaseModel):
    profile_updates: Dict[str, str] = Field(
        default_factory=dict,
        description="Key-value updates representing permanent user details, e.g., name, mail, favorite_city, brother_name."
    )
    vector_memories: List[str] = Field(
        default_factory=list,
        description="List of raw statements/facts to add to the long-term semantic vector database."
    )

# Prompt definition
REFLECTION_PROMPT = """
You are the Self-Learning Reflection Engine.
Your job is to analyze the conversation history and task execution details to identify any new, permanent facts about the user, their preferences, personal info, contacts, or habits.

Input details:
User Prompt: {primary_goal}
Completed Tasks: {completed_tasks}
Final Response: {final_response}

Instructions:
1. Extract any concrete, long-term information about the user.
2. Examples to extract:
   - Preferences: "prefers email communication", "hates scheduling meetings on Mondays", "favorite city is Agra".
   - Contact Info: "sister's email is sister@gmail.com", "brother's name is Rahul".
   - Personal Facts: "working as a developer", "uses hyprland window manager".
3. Do NOT extract temporary task details, errors, or simple queries.
4. Output your response as a structured JSON object matching the requested schema.
If no new long-term facts or preferences are found, return empty structures.
"""

def is_personal_query(query: str) -> bool:
    """Lightweight, highly optimized heuristic check to determine if personal memory retrieval is needed."""
    # Normalize query
    q = query.lower()
    
    # List of terms that clearly indicate personal context is needed
    personal_keywords = [
        "my", "me", "i ", " i'm", " i've", " i'd", " i'll", "myself", "mine",
        "brother", "sister", "father", "mother", "parent", "family", "friend", "rohan", "prithvi",
        "favorite", "college", "university", "school", "major", "academic", "study",
        "email", "mail", "calendar", "event", "task", "todo", "appointment", "meeting",
        "who am i", "my name", "what do you know about", "remember", "recall"
    ]
    
    import re
    # Check if any keyword matches as a word boundary
    for kw in personal_keywords:
        if re.search(r'\b' + re.escape(kw) + r'\b', q):
            return True
            
    return False

def memory_injector_node(state: AgentState):
    print("\n[Node: Memory Injector] Retrieving relevant user context...")
    primary_goal = state.get("primary_goal", "")
    
    # Skip retrieval if the prompt doesn't refer to personal info, preferences, or tasks
    if not is_personal_query(primary_goal):
        print("  -> Personal context not required for this query. Skipping memory retrieval.")
        return {
            "working_memory": {}
        }
    
    # 1. Fetch JSON user profile
    user_profile = {}
    try:
        # Resolve path to memory files (4 levels up from src/CoreFunctions/StateGraph/memory_nodes.py)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        user_info_path = os.path.join(base_dir, "Memory", "user_info.json")
        
        if os.path.exists(user_info_path):
            with open(user_info_path, "r", encoding="utf-8") as f:
                raw_profile = json.load(f)
                # Simplify to standard key-value format for LLM readability
                for key, val_obj in raw_profile.items():
                    if isinstance(val_obj, dict) and "value" in val_obj:
                        user_profile[key] = val_obj["value"]
                    else:
                        user_profile[key] = val_obj
    except Exception as e:
        print(f"  ⚠️ Error loading user profile: {e}")
        
    # 2. Semantic Search over Vector memory
    relevant_memories = []
    try:
        relevant_memories = search_vector(primary_goal, k=3)
    except Exception as e:
        print(f"  ⚠️ Error searching vector memory: {e}")
        
    # 3. Store in working_memory
    working_memory = state.get("working_memory", {}) or {}
    working_memory["user_profile"] = user_profile
    working_memory["relevant_memories"] = relevant_memories
    
    print(f"  -> Injected user profile keys: {list(user_profile.keys())}")
    print(f"  -> Injected {len(relevant_memories)} semantically relevant memories.")
    
    return {
        "working_memory": working_memory
    }

def reflection_node(state: AgentState):
    print("\n[Node: Reflection] Reflecting on conversation to extract knowledge...")
    primary_goal = state.get("primary_goal", "")
    completed_tasks = state.get("completed_tasks", {}) or {}
    final_response = state.get("final_response", "")
    
    # If final response is empty, don't reflect
    if not final_response:
        return {}
        
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0)
        structured_llm = llm.with_structured_output(MemoryReflection)
        
        completed_tasks_str = json.dumps(completed_tasks, indent=2)
        content = f"User Prompt: {primary_goal}\n\nCompleted Tasks:\n{completed_tasks_str}\n\nFinal Response:\n{final_response}"
        
        reflection: MemoryReflection = structured_llm.invoke([
            SystemMessage(content=REFLECTION_PROMPT),
            HumanMessage(content=content)
        ])
        
        # 1. Update Profile (user_info.json)
        profile_updates = reflection.profile_updates
        if profile_updates:
            print("\n🧠 \033[1;34mAutomatic Profile Updates Learnt:\033[0m")
            for key, val in profile_updates.items():
                store_memory("user", key, val)
                print(f"  \033[32m✔\033[0m Learnt: {key} = {val}")
                
        # 2. Update Vector Memories
        vector_memories = reflection.vector_memories
        if vector_memories:
            print("\n🧠 \033[1;34mAutomatic Facts/Memories Learnt:\033[0m")
            for mem in vector_memories:
                store_vector(mem)
                print(f"  \033[32m✔\033[0m Stored: \"{mem}\"")
                
    except Exception as e:
        print(f"  ⚠️ Error during reflection: {e}")
        
    return {}
