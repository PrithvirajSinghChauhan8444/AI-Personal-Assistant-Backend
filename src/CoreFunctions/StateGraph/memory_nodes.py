import os
import sys
import json
import re
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.CoreFunctions.memory import store_memory, fetch_memory
from src.CoreFunctions.vector_memory import store_vector, search_vector
from src.CoreFunctions.StateGraph.state import AgentState

# Pydantic Model for Hermes Skills
class SkillDocument(BaseModel):
    name: str = Field(
        description="Name of the skill in lowercase-kebab-case (e.g. gmail-multiaccount-handling, classroom-coursework-checks)."
    )
    description: str = Field(
        description="A concise 1-2 sentence description of what this skill allows the agent to do."
    )
    category: str = Field(
        description="Category of the skill (e.g., productivity, development, communication)."
    )
    tags: List[str] = Field(
        default_factory=list,
        description="List of related keywords/tags to match user queries."
    )
    procedure: str = Field(
        description="Markdown step-by-step instructions on how to perform this workflow, including command examples or APIs."
    )

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
    new_skills: List[SkillDocument] = Field(
        default_factory=list,
        description="Autonomous procedural skill manuals extracted from successfully executed workflows for future reusability."
    )

# Prompt definition
REFLECTION_PROMPT = """
You are the Hermes Self-Learning Reflection & Skill Extraction Engine.
Your job is to analyze the conversation history and successfully executed tasks to:
1. Extract any new, permanent facts or preferences about the user.
2. Extract and compile reusable procedural **"Skills"** if a complex workflow or multi-step task was successfully accomplished (e.g., configuring multi-account authorization, checking specialized coursework, complex terminal pipelines). 

Input details:
User Prompt: {primary_goal}
Completed Tasks: {completed_tasks}
Final Response: {final_response}

Instructions for Skill Extraction:
- If a task was successful and repeatable, define a new procedural Skill!
- Give it a name like 'gmail-searching' or 'classroom-management'.
- Write a step-by-step 'procedure' explaining exactly what commands, APIs, or tools were utilized and how to replicate the success.
- If no complex workflow was run, keep new_skills empty.
"""

def is_personal_query(query: str) -> bool:
    """Lightweight check to determine if personal memory/skills context is needed."""
    q = query.lower()
    
    personal_keywords = [
        "my", "me", "i ", " i'm", " i've", " i'd", " i'll", "myself", "mine",
        "brother", "sister", "father", "mother", "parent", "family", "friend", "rohan", "prithvi",
        "favorite", "college", "university", "school", "major", "academic", "study",
        "email", "mail", "calendar", "event", "task", "todo", "appointment", "meeting",
        "who am i", "my name", "what do you know about", "remember", "recall", "skills", "skill"
    ]
    
    for kw in personal_keywords:
        if re.search(r'\b' + re.escape(kw) + r'\b', q):
            return True
            
    return False

def check_fast_path(primary_goal: str) -> Optional[str]:
    """
    Checks if a prompt can be resolved instantly via Fast-Path direct tool calls.
    Returns the final response string if matched and processed, otherwise None.
    """
    q = primary_goal.strip().lower()
    
    # 1. Matches: "remember that [fact]" or "save that [fact]"
    match_remember_that = re.match(r'^(remember|save)\s+that\s+(.*)', q, re.IGNORECASE)
    if match_remember_that:
        fact = primary_goal.strip()[match_remember_that.start(2):]
        # Store in vector store
        store_vector(fact)
        return f"Got it! I've saved that fact in your long-term memory."
        
    # 2. Matches: "remember my [key] is [value]" or "remember [key] as [value]"
    match_remember_keyval = re.match(r'^remember\s+(my\s+)?([\w\s_]+?)\s+(is|as)\s+(.*)', q, re.IGNORECASE)
    if match_remember_keyval:
        key = match_remember_keyval.group(2).strip()
        val = match_remember_keyval.group(4).strip()
        # Store in structured memory
        store_memory("past", key, val)
        return f"Got it! I have saved that your {key} is {val}."

    # 3. Matches simple direct recalls: "what do you know about [topic]" or "recall [topic]" or "who is [topic]"
    match_recall = re.match(r'^(what\s+do\s+you\s+know\s+about|recall|who\s+is|what\s+is\s+my)\s+(.*)', q, re.IGNORECASE)
    if match_recall:
        topic = match_recall.group(2).strip().rstrip('?')
        # 1. Search structured memory first
        structured_val = fetch_memory(None, topic)
        if structured_val:
            return f"I recall that your {topic} is: {structured_val}."
            
        # 2. Search vector database semantically
        vector_results = search_vector(topic, k=2)
        if vector_results:
            summary = "\n".join([f"- {res}" for res in vector_results])
            return f"Here is what I remember about '{topic}':\n{summary}"

    return None

def memory_injector_node(state: AgentState):
    print("\n[Node: Memory Injector] Retrieving relevant user context & skills...")
    primary_goal = state.get("primary_goal", "")
    
    # 0. Check Fast-Path (Phase 2 Speed Optimization)
    fast_path_response = check_fast_path(primary_goal)
    if fast_path_response:
        working_memory = state.get("working_memory", {}) or {}
        working_memory["fast_path_matched"] = True
        return {
            "working_memory": working_memory,
            "final_response": fast_path_response
        }
    
    # 1. Base Workspace Directories
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    skills_dir = os.path.join(base_dir, "Skills")
    
    # 2. Level 0 & Level 1 Skills Ingestion (Progressive Disclosure)
    active_skills_content = []
    available_skills_index = []
    
    if os.path.exists(skills_dir) and os.path.isdir(skills_dir):
        for item in os.listdir(skills_dir):
            skill_folder = os.path.join(skills_dir, item)
            skill_file = os.path.join(skill_folder, "SKILL.md")
            if os.path.isdir(skill_folder) and os.path.exists(skill_file):
                try:
                    with open(skill_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                    # Extract YAML frontmatter
                    meta_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                    name = item
                    description = ""
                    tags = []
                    
                    if meta_match:
                        meta_text = meta_match.group(1)
                        # Simple parsing of name, description, tags from YAML
                        name_match = re.search(r'name:\s*(.*)', meta_text)
                        if name_match: name = name_match.group(1).strip()
                        
                        desc_match = re.search(r'description:\s*(.*)', meta_text)
                        if desc_match: description = desc_match.group(1).strip()
                        
                        tags_match = re.search(r'tags:\s*\[(.*?)\]', meta_text)
                        if tags_match:
                            tags = [t.strip().strip('"').strip("'") for t in tags_match.group(1).split(",")]
                    
                    available_skills_index.append({
                        "name": name,
                        "description": description,
                        "tags": tags,
                        "path": skill_file
                    })
                except Exception as e:
                    print(f"  ⚠️ Error loading skill metadata for {item}: {e}")

    # Level 1 Loading: If prompt matches tags or name, load full procedural skill
    q = primary_goal.lower()
    for skill in available_skills_index:
        matched = False
        if skill["name"].lower() in q:
            matched = True
        else:
            for tag in skill["tags"]:
                if tag.lower() in q:
                    matched = True
                    break
        
        if matched:
            try:
                with open(skill["path"], "r", encoding="utf-8") as f:
                    full_content = f.read()
                active_skills_content.append(full_content)
                print(f"  \033[32m✔\033[0m Loaded Skill: {skill['name']} (Level 1 Disclosure)")
            except Exception as e:
                print(f"  ⚠️ Error reading full skill file {skill['name']}: {e}")

    # 3. Store injected skills in working memory
    working_memory = state.get("working_memory", {}) or {}
    working_memory["active_skills"] = active_skills_content
    working_memory["skills_index"] = [s["name"] for s in available_skills_index]

    if not is_personal_query(primary_goal):
        print("  -> Personal profile context not required. Skipping user info retrieval.")
        return {
            "working_memory": working_memory
        }
    
    # 4. Fetch JSON user profile
    user_profile = {}
    try:
        user_info_path = os.path.join(base_dir, "Memory", "user_info.json")
        if os.path.exists(user_info_path):
            with open(user_info_path, "r", encoding="utf-8") as f:
                raw_profile = json.load(f)
                for key, val_obj in raw_profile.items():
                    if isinstance(val_obj, dict) and "value" in val_obj:
                        user_profile[key] = val_obj["value"]
                    else:
                        user_profile[key] = val_obj
    except Exception as e:
        print(f"  ⚠️ Error loading user profile: {e}")
        
    # 5. Semantic Search over Vector memory
    relevant_memories = []
    try:
        relevant_memories = search_vector(primary_goal, k=3)
    except Exception as e:
        print(f"  ⚠️ Error searching vector memory: {e}")
        
    working_memory["user_profile"] = user_profile
    working_memory["relevant_memories"] = relevant_memories
    
    print(f"  -> Injected user profile keys: {list(user_profile.keys())}")
    print(f"  -> Injected {len(relevant_memories)} semantically relevant memories.")
    
    return {
        "working_memory": working_memory
    }

def reflection_node(state: AgentState):
    print("\n[Node: Reflection] Reflecting on conversation & extracting Hermes Skills...")
    primary_goal = state.get("primary_goal", "")
    completed_tasks = state.get("completed_tasks", {}) or {}
    final_response = state.get("final_response", "")
    
    if not final_response:
        return {}
        
    try:
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model="gemma4:e2b", temperature=0)
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
                
        # 3. Save new extracted Skills (Nous Research Skills Framework)
        new_skills = reflection.new_skills
        if new_skills:
            print("\n🛠️ \033[1;36mExtracted Reusable Skill Documents (Hermes Loop):\033[0m")
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            skills_dir = os.path.join(base_dir, "Skills")
            os.makedirs(skills_dir, exist_ok=True)
            
            for skill in new_skills:
                skill_folder = os.path.join(skills_dir, skill.name)
                os.makedirs(skill_folder, exist_ok=True)
                skill_path = os.path.join(skill_folder, "SKILL.md")
                
                tags_str = ", ".join([f'"{t}"' for t in skill.tags])
                
                # Format to Nous Research standard frontmatter + markdown
                skill_markdown = f"""---
name: {skill.name}
description: "{skill.description}"
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: {skill.category}
    tags: [{tags_str}]
---
# {skill.name.replace("-", " ").title()}

## When to Use
Use this skill when you need to execute workflows related to {", ".join(skill.tags)}.

## Procedure
{skill.procedure}
"""
                with open(skill_path, "w", encoding="utf-8") as f:
                    f.write(skill_markdown.strip())
                print(f"  \033[32m✔\033[0m Saved Skill document: Skills/{skill.name}/SKILL.md")
                
    except Exception as e:
        print(f"  ⚠️ Error during reflection/skill extraction: {e}")
        
    return {}
