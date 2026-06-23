import os
import sys
import json
import re
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
        description="Markdown step-by-step instructions on how to perform this workflow. Must include references to the automated helper script if one is generated."
    )
    script_code: Optional[str] = Field(
        default=None,
        description="An optional Python or Bash script code that automates the procedure. If the workflow can be programmed to bypass complex worker actions (e.g. API calls, file editing, parsing, terminal commands), provide the full script code here. Otherwise, leave null."
    )
    script_filename: Optional[str] = Field(
        default=None,
        description="The filename of the automation script if script_code is provided (e.g., 'reorganize.py', 'sync_data.sh')."
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
2. Extract and compile reusable procedural **"Skills"** ONLY if a novel, complex, and highly reusable workflow or multi-step task was successfully accomplished (e.g., configuring multi-account authorization, checking specialized coursework, complex terminal pipelines, advanced browser automation).

Input details:
User Prompt: {primary_goal}
Completed Tasks: {completed_tasks}
Final Response: {final_response}

Instructions for Skill Extraction:
- **CRITICAL RESTRICTION**: Do NOT create a skill for every task. Keep `new_skills` EMPTY for standard/simple tasks, or for one-off tasks that are highly specific (e.g., classifying a specific agent, looking up a specific github user, writing a single one-off python script, retrieving user profile details).
- **GENERALIZATION REQUIREMENT**: A skill MUST represent a generalized capability that makes the system faster and more efficient at handling FUTURE, broader classes of queries. It should not be a log/recap of the specific task that was run.
- **AUTOMATION SCRIPT BYPASS**: Whenever possible, if the workflow/procedure can be automated using a helper Python script or Bash script (e.g., to query APIs, manipulate local files, scan directories, perform structured lookups) to bypass long multi-agent planning/tool calls, write the full script in `script_code` and name it in `script_filename`. Ensure the markdown `procedure` in the `SKILL.md` file explicitly describes how the agent should run this script (e.g., using `python3` or `bash` and correct relative paths) to bypass the long manual process.
- **EXAMPLE CRITERIA**:
  - BAD SKILL (Too specific / simple): `hermes-agent-classification` (steps to classify the agent), `github-profile-status-check` (steps to check a user's github status), `python-script-generation-and-delivery` (steps to write and email a script).
  - GOOD SKILL (Generalized / reusable): `browser-based-knowledge-retrieval` (how to search google using the browser agent and read page content to learn about unknown concepts/topics), `multi-account-email-handling` (how to manage multiple email sessions).
- If you do extract a Skill:
  - Give it a generalized name in lowercase-kebab-case (e.g. 'browser-information-retrieval', 'obsidian-vault-refactoring').
  - Assign it a descriptive category (e.g. 'dev-utils', 'information-retrieval', 'productivity', 'communication').
  - Ensure the 'procedure' is written as generic markdown step-by-step instructions. Explain exactly how future agents should run the automated script (if generated) or utilize specific tools, commands, or APIs to speed up execution.
- If no complex, generalized workflow was run, keep `new_skills` empty.
"""

def is_personal_query(query: str) -> bool:
    """Lightweight check to determine if personal memory/skills context is needed."""
    q = query.lower()
    
    personal_keywords = [
        "my", "me", "i ", " i'm", " i've", " i'd", " i'll", "myself", "mine",
        "brother", "sister", "father", "mother", "parent", "family", "friend", "rohan", "prithvi",
        "favorite", "college", "university", "school", "major", "academic", "study",
        "email", "mail", "calendar", "event", "task", "todo", "appointment", "meeting",
        "who am i", "my name", "what do you know about", "remember", "recall", "skills", "skill",
        "memory", "unified memory", "stored", "saved", "preference", "preferences"
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
            
        # 2. Search vector database semantically (with threshold filtering)
        vector_results = search_vector(topic, k=2, threshold=1.15)
        if vector_results:
            summary = "\n".join([f"- {res}" for res in vector_results])
            return f"Here is what I remember about '{topic}':\n{summary}"

    return None

def memory_injector_node(state: AgentState):
    from src.CoreFunctions.logger import log_node_start, log_node_end, log_message
    log_node_start("MemoryInjector", state)
    
    print("\n[Node: Memory Injector] Retrieving relevant user context & skills...")
    primary_goal = state.get("primary_goal", "")
    
    # 0. Check Fast-Path (Phase 2 Speed Optimization)
    fast_path_response = check_fast_path(primary_goal)
    working_memory = state.get("working_memory", {}) or {}
    
    if fast_path_response:
        working_memory["fast_path_matched"] = True
        output_state = {
            "working_memory": working_memory,
            "final_response": fast_path_response
        }
        log_node_end("MemoryInjector", output_state)
        return output_state
    else:
        # Reset fast path flag for this turn to prevent state pollution from previous turns
        working_memory["fast_path_matched"] = False
    
    # 2. Level 0 & Level 1 Skills Ingestion (Progressive Disclosure via Semantic Vector Search)
    active_skills_content = []
    
    from src.CoreFunctions.vector_memory import search_skills_vector, _load_skills_data
    
    # Retrieve semantically matching skills
    matched_skills = search_skills_vector(primary_goal, k=2)
    for skill in matched_skills:
        try:
            with open(skill["path"], "r", encoding="utf-8") as f:
                full_content = f.read()
            active_skills_content.append(full_content)
            print(f"  \033[32m✔\033[0m Loaded Skill Semantically: {skill['name']} (Vector Similarity match)")
        except Exception as e:
            print(f"  ⚠️ Error reading semantically matched skill file {skill['name']}: {e}")

    # Retrieve all available skill names for global index metadata
    all_skills_data = _load_skills_data()
    all_skill_names = [s["name"] for s in all_skills_data]

    # 3. Store injected skills in working memory
    working_memory = state.get("working_memory", {}) or {}
    working_memory["active_skills"] = active_skills_content
    working_memory["skills_index"] = all_skill_names

    if not is_personal_query(primary_goal):
        print("  -> Personal profile context not required. Skipping user info retrieval.")
        return {
            "working_memory": working_memory
        }
    
    # 4. Fetch User Profile & Stored Memories from Unified Database Memory
    user_profile = {}
    try:
        for category in ["user", "past", "current"]:
            raw_mem = fetch_memory(category)
            if raw_mem:
                for key, val_obj in raw_mem.items():
                    val = val_obj.get("value") if isinstance(val_obj, dict) else val_obj
                    user_profile[key] = val
                    user_profile[f"{category}:{key}"] = val
    except Exception as e:
        print(f"  ⚠️ Error loading unified memory: {e}")
        
    # 5. Semantic Search over Vector memory
    relevant_memories = []
    try:
        relevant_memories = search_vector(primary_goal, k=5)
    except Exception as e:
        print(f"  ⚠️ Error searching vector memory: {e}")
        
    # --- CONTEXT WINDOW BUDGETING & LATENCY CONTROL ---
    # Hard budget limit of ~800 tokens (~3200 characters) to prevent context overflows
    max_char_budget = 3200
    current_char_count = 0
    
    budget_user_profile = {}
    for key, val in user_profile.items():
        if ":" in key:
            serialized_fact = f"{key}: {val}\n"
            fact_len = len(serialized_fact)
            if current_char_count + fact_len <= max_char_budget:
                budget_user_profile[key] = val
                base_key = key.split(":", 1)[1]
                budget_user_profile[base_key] = val
                current_char_count += fact_len
            else:
                break
        elif f"user:{key}" not in user_profile and f"past:{key}" not in user_profile and f"current:{key}" not in user_profile:
            serialized_fact = f"{key}: {val}\n"
            fact_len = len(serialized_fact)
            if current_char_count + fact_len <= max_char_budget:
                budget_user_profile[key] = val
                current_char_count += fact_len
            else:
                break

    budget_relevant_memories = []
    for mem in relevant_memories:
        serialized_mem = f"- {mem}\n"
        mem_len = len(serialized_mem)
        if current_char_count + mem_len <= max_char_budget:
            budget_relevant_memories.append(mem)
            current_char_count += mem_len
        else:
            print(f"  ⚠️ [Context Budget] Reached character budget limit ({current_char_count}/{max_char_budget}). Truncating remaining memories.")
            break
            
    user_profile = budget_user_profile
    relevant_memories = budget_relevant_memories
        
    working_memory["user_profile"] = user_profile
    working_memory["relevant_memories"] = relevant_memories
    
    print(f"  -> Injected user profile keys: {list(user_profile.keys())}")
    print(f"  -> Injected {len(relevant_memories)} semantically relevant memories.")
    
    output_state = {
        "working_memory": working_memory
    }
    log_node_end("MemoryInjector", output_state)
    return output_state

def reflection_node(state: AgentState):
    def print(*args, sep=" ", end="\n", file=None, flush=True):
        import threading
        message = sep.join(map(str, args))
        if threading.current_thread() is not threading.main_thread():
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                log_path = os.path.join(base_dir, "Memory", "reflection.log")
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(message + end)
            except Exception:
                pass
        else:
            import sys
            sys.stdout.write(message + end)
            if flush:
                sys.stdout.flush()

    from src.CoreFunctions.logger import log_node_start, log_node_end, log_error, log_message
    log_node_start("Reflection", state)

    print("\n[Node: Reflection] Reflecting on conversation & extracting Hermes Skills...")
    primary_goal = state.get("primary_goal", "")
    completed_tasks = state.get("completed_tasks", {}) or {}
    final_response = state.get("final_response", "")
    
    if not final_response:
        log_node_end("Reflection", {})
        return {}
        
    try:
        from langchain_ollama import ChatOllama
        model_name = "gemma4:e4b"
        log_message(f"Reflection: Invoking model {model_name} for self-reflection & skill extraction.")
        llm = ChatOllama(model=model_name, temperature=0)
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
                # Clean category name for folder
                clean_category = re.sub(r'[^a-zA-Z0-9_-]', '-', skill.category.strip().lower())
                if not clean_category:
                    clean_category = "general"
                
                skill_folder = os.path.join(skills_dir, clean_category, skill.name)
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
                print(f"  \033[32m✔\033[0m Saved Skill document: Skills/{clean_category}/{skill.name}/SKILL.md")
                
                # If script is generated, save it in scripts/
                if skill.script_code and skill.script_filename:
                    scripts_folder = os.path.join(skill_folder, "scripts")
                    os.makedirs(scripts_folder, exist_ok=True)
                    script_path = os.path.join(scripts_folder, skill.script_filename)
                    with open(script_path, "w", encoding="utf-8") as f_script:
                        f_script.write(skill.script_code.strip())
                    print(f"  \033[32m✔\033[0m Saved Automation Script: Skills/{clean_category}/{skill.name}/scripts/{skill.script_filename}")
                
    except Exception as e:
        print(f"  ⚠️ Error during reflection/skill extraction: {e}")
        log_error("Reflection", str(e))
        
    log_node_end("Reflection", {})
    return {}

from typing import Literal
import threading
import time

class FeedbackPreference(BaseModel):
    target_worker: str = Field(
        description="Name of the worker this feedback applies to. Must match one of the active worker names exactly (e.g., 'ObsidianNoteWorker', 'GmailWorker', 'SystemWorker', 'BrowserWorker', 'ProductivityWorker', 'ClassroomWorker', 'MiscWorker')."
    )
    scope: Literal["once", "session", "persistent"] = Field(
        description="Scope of preference: 'once' (apply to the very next run only), 'session' (apply during this chat session), or 'persistent' (long-term preference)."
    )
    preference: str = Field(
        description="A concise, actionable instruction/rule for the target worker."
    )

def trigger_feedback_extraction(user_input: str, final_response: str, feedback: str):
    """Spawns a background thread to analyze and extract worker tuning preference without blocking CLI."""
    def run_extraction():
        try:
            from langchain_ollama import ChatOllama
            from src.CoreFunctions.unified_memory import UnifiedMemory
            from src.CoreFunctions.StateGraph.registry import WorkerRegistry
            
            um = UnifiedMemory()
            if not um.enabled:
                return
                
            model_name = "gemma4:e4b"
            llm = ChatOllama(model=model_name, temperature=0)
            structured_llm = llm.with_structured_output(FeedbackPreference)
            
            prompt = f"""You are the Behavior Tuning Preference Extractor.
Your job is to analyze:
1. The user's original goal/prompt: "{user_input}"
2. The assistant's completed response: "{final_response}"
3. The user's corrective feedback/preference: "{feedback}"

Identify which specific worker this feedback targets. The active workers are:
{", ".join(WorkerRegistry.get_worker_names())}

Categorize the scope of the instruction:
- 'once': A one-off instruction/tweak specifically for the next time this type of task is run.
- 'session': A general rule to be followed during the current chat session.
- 'persistent': A long-term preference, habit, or strict rule.

Extract the preference as a clear, concise instruction.
"""
            
            preference_data: FeedbackPreference = structured_llm.invoke([
                SystemMessage(content=prompt)
            ])
            
            extracted_worker = preference_data.target_worker.strip()
            active_names = WorkerRegistry.get_worker_names()
            
            worker_name = None
            
            # 1. Exact match
            if extracted_worker in active_names:
                worker_name = extracted_worker
                
            # 2. Case-insensitive and space-normalization match
            if not worker_name:
                normalized_target = extracted_worker.lower().replace(" ", "").replace("_", "").replace("-", "")
                normalized_target = normalized_target.replace("worker", "")
                
                for name in active_names:
                    norm_active = name.lower().replace(" ", "").replace("_", "").replace("-", "").replace("worker", "")
                    if normalized_target == norm_active:
                        worker_name = name
                        break
            
            # 3. Fuzzy match fallback
            if not worker_name:
                import difflib
                close_matches = difflib.get_close_matches(extracted_worker, active_names, n=1, cutoff=0.5)
                if close_matches:
                    worker_name = close_matches[0]
                    
            # 4. Keyword heuristic fallback
            if not worker_name:
                lowered_feedback = (feedback.lower() + " " + preference_data.preference.lower() + " " + extracted_worker.lower())
                if any(x in lowered_feedback for x in ["drive", "download", "google drive"]):
                    worker_name = "GoogleDriveWorker"
                elif any(x in lowered_feedback for x in ["gmail", "email", "mail"]):
                    worker_name = "GmailWorker"
                elif any(x in lowered_feedback for x in ["browser", "web", "page", "url"]):
                    worker_name = "BrowserWorker"
                elif any(x in lowered_feedback for x in ["classroom", "course"]):
                    worker_name = "ClassroomWorker"
                elif any(x in lowered_feedback for x in ["github", "git", "repo"]):
                    worker_name = "GithubWorker"
                elif any(x in lowered_feedback for x in ["system", "terminal", "command", "process"]):
                    worker_name = "SystemWorker"
                else:
                    worker_name = "MiscWorker"
            
            if worker_name:
                db_key = f"worker_feedback:{worker_name}"
                existing = um.retrieve_memory(db_key) or {}
                
                new_pref = {
                    "preference": preference_data.preference,
                    "scope": preference_data.scope,
                    "timestamp": time.time()
                }
                
                preferences_list = existing.get("preferences", [])
                preferences_list.append(new_pref)
                
                is_persistent = preference_data.scope == "persistent"
                um.store_memory(
                    db_key,
                    {"preferences": preferences_list},
                    persistent=is_persistent
                )
                print(f"\n🧠 [Feedback Loop] Learnt preference for '{worker_name}' (extracted: '{extracted_worker}'): \"{preference_data.preference}\" (Scope: {preference_data.scope})")
            else:
                print(f"\n⚠️ [Feedback Loop] Ignored feedback: Extracted worker '{extracted_worker}' is not in active workers list.")
        except Exception as e:
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                log_path = os.path.join(base_dir, "Memory", "reflection.log")
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"\nFeedback Loop Extraction Error: {e}\n")
            except Exception:
                pass

    thread = threading.Thread(target=run_extraction, daemon=True)
    thread.start()
