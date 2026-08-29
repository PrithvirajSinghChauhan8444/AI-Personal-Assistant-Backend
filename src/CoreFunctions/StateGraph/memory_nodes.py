import os
import sys
import json
import re
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector
from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory
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
from typing import Literal

class ProfileFact(BaseModel):
    value: str = Field(description="The value of the profile fact.")
    source: Literal["stated", "inferred", "derived"] = Field(
        description="Source of the fact: 'stated' if explicitly said by user, 'inferred' if analyzed/guessed from user behavior/conversation, 'derived' if computed or looked up."
    )

class PersonUpdate(BaseModel):
    name: str = Field(description="Name of the person.")
    relation: Optional[str] = Field("", description="Relationship type (e.g. brother, friend, colleague).")
    email: Optional[str] = Field("", description="Email address.")
    phone: Optional[str] = Field("", description="Phone number.")
    notes: Optional[str] = Field("", description="Free-text notes about this person (like school, job, details).")

class EventLogged(BaseModel):
    event_type: str = Field(description="Type of the event (e.g., 'task_completion', 'preference_change', 'meeting', 'error_resolution').")
    summary: str = Field(description="Concise description/summary of what happened.")
    ref_id: Optional[str] = Field("", description="Optional reference ID, e.g. commit hash, task ID, or email thread ID.")

class MemoryReflection(BaseModel):
    canonical_updates: Dict[str, ProfileFact] = Field(
        default_factory=dict,
        description="Profile updates for canonical fields: name, email, hometown, favorite_city. The values MUST be ProfileFact objects."
    )
    unrecognized_updates: Dict[str, ProfileFact] = Field(
        default_factory=dict,
        description="Profile updates that do not match the canonical fields (name, email, hometown, favorite_city). These will be routed to a review queue."
    )
    people_updates: List[PersonUpdate] = Field(
        default_factory=list,
        description="Updates to the user's social connections / contacts (people they know: friends, family, colleagues, etc.)."
    )
    events: List[EventLogged] = Field(
        default_factory=list,
        description="List of meaningful real-world events or milestones completed during this run to log in the timeline."
    )
    vector_memories: List[ProfileFact] = Field(
        default_factory=list,
        description="List of raw statements/facts to add to the long-term semantic vector database."
    )
    superseded_facts: List[str] = Field(
        default_factory=list,
        description="List of exact existing facts or profile values that are now contradicted/superseded by the new facts (e.g., if the user moved to Bangalore, the old fact 'lives in Pune' is superseded and should be listed here)."
    )
    new_skills: List[SkillDocument] = Field(
        default_factory=list,
        description="Autonomous procedural skill manuals extracted from successfully executed workflows for future reusability."
    )

# Prompt definition
REFLECTION_PROMPT = """
You are the Hermes Self-Learning Reflection & Skill Extraction Engine.
Your job is to analyze the conversation history, successfully executed tasks, and existing memory state to:
1. Extract any new, permanent facts or preferences about the user.
2. Route facts logically:
   - Profile details matching 'name', 'email', 'hometown', or 'favorite_city' go to `canonical_updates`.
   - Other permanent user attributes (e.g. education, career, minor details) go to `unrecognized_updates`.
   - Social contacts/connections (friends, family, brother, colleagues) go to `people_updates`.
   - Meaningful milestones, tasks completed, or real-world events completed in this session go to `events` (timeline events).
   - General semantic facts (e.g. preferences, habits, facts) go to `vector_memories`.
3. Provide a provenance `source` attribute ('stated', 'inferred', or 'derived') for every extracted fact or profile detail.
4. Clean up contradictions and handle deletions/denials:
   - Compare new updates against the "Existing Memory State" provided. If any new fact contradicts an existing fact, put the exact text/value of the stale existing fact in `superseded_facts` so it can be purged.
   - **CRITICAL - Handling Deletions & Denials**: If the user explicitly denies a fact, requests deletion of a fact/association, or states that certain info is wrong/incorrect (e.g., "I don't use eprithvi22", "remove my github handle", "I am not related to eprithvi22"):
     1. Do **NOT** extract or add a new fact recording this request (e.g., do NOT add "User requested removal of eprithvi22" or "User is not related to eprithvi22" to `vector_memories` or profiles).
     2. Identify any and all matching/related facts in the "Existing Memory State" (e.g., "Prithviraj's GitHub handle is eprithvi22", "User's GitHub username is eprithvi22...") and put their **exact text** in `superseded_facts` to remove them from the database immediately.
   - **CRITICAL - Topic-based Stale Fact Purging**: When a key attribute or entity identifier (such as a GitHub handle, email address, phone number, location, or full name) is verified, corrected, or resolved:
     1. Identify **ALL** old, conflicting, or outdated facts, guesses, and previous denial records (e.g. "User is not associated with GitHub username 'eprithvi22'", "Prithviraj's GitHub handle is eprithvi22") related to that specific topic in the "Existing Memory State".
     2. Put the **exact text** of all those stale/conflicting facts and denials in `superseded_facts` to purge them completely. Only the single, verified, current correct fact should remain in active memory.
5. Extract and compile reusable procedural **"Skills"** ONLY if a novel, complex, and highly reusable workflow or multi-step task was successfully accomplished (e.g., configuring multi-account authorization, checking specialized coursework, complex terminal pipelines, advanced browser automation).

Instructions for Skill Extraction:
- **CRITICAL RESTRICTION**: Do NOT create a skill for every task. Keep `new_skills` EMPTY for standard/simple tasks, or for one-off tasks that are highly specific.
- **GENERALIZATION REQUIREMENT**: A skill MUST represent a generalized capability that makes the system faster and more efficient at handling FUTURE queries.
- **AUTOMATION SCRIPT BYPASS**: Whenever possible, if the workflow/procedure can be automated using a helper script, write the full script in `script_code` and name it in `script_filename`.
"""



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
    from src.CoreFunctions.Infrastructure.logger import log_node_start, log_node_end, log_message
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
    
    from src.CoreFunctions.Infrastructure.vector_memory import search_skills_vector, _load_skills_data
    
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


    # 4. Fetch User Profile & Stored Memories from Unified Database Memory
    user_profile = {}
    um = UnifiedMemory()
    try:
        # Load from relational profile table
        profile_db = um.engine.query_profile()
        for p in profile_db:
            user_profile[p["key"]] = p["value"]
            user_profile[f"user:{p['key']}"] = p["value"]
            
        # Load legacy cache categories
        for category in ["user", "past", "current"]:
            raw_mem = fetch_memory(category)
            if raw_mem:
                for key, val_obj in raw_mem.items():
                    val = val_obj.get("value") if isinstance(val_obj, dict) else val_obj
                    if key not in user_profile:
                        user_profile[key] = val
                    if f"{category}:{key}" not in user_profile:
                        user_profile[f"{category}:{key}"] = val
                        
        # Load Social Connections / People CRM
        connections = um.engine.query_people()
        if connections:
            social_connections = []
            for c in connections:
                social_connections.append(f"{c['name'].title()} ({c['relation']}): Email={c['email']}, Phone={c['phone']}, Notes={c['notes']}")
            user_profile["social_connections"] = "; ".join(social_connections)
            
        # Load Recent Timeline Events (Episodic)
        events_db = um.engine.query_events(limit=5)
        if events_db:
            recent_events = []
            for e in events_db:
                import time
                time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(e['timestamp']))
                recent_events.append(f"[{time_str}] {e['event_type']}: {e['summary']}")
            user_profile["recent_events"] = "; ".join(recent_events)
            
    except Exception as e:
        print(f"  ⚠️ Error loading unified memory: {e}")
        
    # 5. Semantic Search over Vector memory with distance threshold filtering
    relevant_memories = []
    try:
        relevant_memories = search_vector(primary_goal, k=5, threshold=1.15)
    except Exception as e:
        print(f"  ⚠️ Error searching vector memory: {e}")
        
    # --- CONTEXT WINDOW BUDGETING & LATENCY CONTROL ---
    # Hard budget limit of ~10,000 tokens (~40,000 characters) to prevent context overflows
    max_char_budget = 40000
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

    from src.CoreFunctions.Infrastructure.logger import log_node_start, log_node_end, log_error, log_message
    log_node_start("Reflection", state)

    print("\n[Node: Reflection] Reflecting on conversation & extracting Hermes Skills...")
    primary_goal = state.get("primary_goal", "")
    completed_tasks = state.get("completed_tasks", {}) or {}
    final_response = state.get("final_response", "")
    
    if not final_response:
        log_node_end("Reflection", {})
        return {}
        
    try:
        from src.CoreFunctions.Infrastructure.llm_factory import get_llm
        llm = None
        local_model = os.environ.get("OLLAMA_MODEL")
        if local_model:
            try:
                from langchain_ollama import ChatOllama
                test_llm = ChatOllama(model=local_model, temperature=0)
                test_llm.invoke("ping")
                llm = test_llm
                print(f"  Using local model '{local_model}' for reflection.")
            except Exception:
                pass
        
        if llm is None:
            llm = get_llm()
            print("  Using default workspace model for reflection.")
            
        structured_llm = llm.with_structured_output(MemoryReflection)
        
        # Fetch current memory state to inject as context
        um = UnifiedMemory()
        existing_profile = um.engine.query_profile()
        existing_facts = um.engine.list_vector_facts()
        existing_people = um.engine.query_people()
        
        profile_summary = "\n".join([f"- {p['key']}: {p['value']} (Source: {p['source']})" for p in existing_profile])
        facts_summary = "\n".join([f"- {f['fact']} (Source: {f['source']})" for f in existing_facts])
        people_summary = "\n".join([f"- {peop['name']}: relation={peop['relation']}, email={peop['email']}, notes={peop['notes']}" for peop in existing_people])
        
        state_context = (
            f"=== Existing Memory State ===\n"
            f"Current Profile Fields:\n{profile_summary or 'None'}\n\n"
            f"Current Vector Facts:\n{facts_summary or 'None'}\n\n"
            f"Current Social Connections:\n{people_summary or 'None'}"
        )
        
        completed_tasks_str = json.dumps(completed_tasks, indent=2)
        content = (
            f"User Prompt: {primary_goal}\n\n"
            f"Completed Tasks:\n{completed_tasks_str}\n\n"
            f"Final Response:\n{final_response}\n\n"
            f"{state_context}"
        )
        
        reflection: MemoryReflection = structured_llm.invoke([
            SystemMessage(content=REFLECTION_PROMPT),
            HumanMessage(content=content)
        ])
        
        # 1. Update Canonical Profile
        canonical_updates = reflection.canonical_updates
        if canonical_updates:
            print("\n🧠 \033[1;34mAutomatic Canonical Profile Updates Learnt:\033[0m")
            for key, fact in canonical_updates.items():
                # Store in relational profile table
                um.engine.upsert_profile(key, fact.value, fact.source)
                # Keep legacy cache in sync
                store_memory("user", key, fact.value)
                print(f"  \033[32m✔\033[0m Learnt: {key} = {fact.value} (Source: {fact.source})")
                
        # 2. Update Unrecognized Profile (Review Queue)
        unrecognized_updates = reflection.unrecognized_updates
        if unrecognized_updates:
            print("\n🧠 \033[1;34mAutomatic Unrecognized Profile Updates Routed to Review Queue:\033[0m")
            for key, fact in unrecognized_updates.items():
                um.engine.add_to_profile_review(key, fact.value, fact.source)
                print(f"  \033[32m✔\033[0m Routed: {key} = {fact.value} (Source: {fact.source})")

        # 3. Update People (CRM)
        people_updates = reflection.people_updates
        if people_updates:
            print("\n🧠 \033[1;34mAutomatic Contact Updates (CRM) Learnt:\033[0m")
            for p in people_updates:
                um.engine.upsert_person(p.name, p.relation, p.email, p.phone, p.notes)
                print(f"  \033[32m✔\033[0m CRM: {p.name} ({p.relation}) - Email: {p.email}")

        # 4. Log Events (Timeline)
        events = reflection.events
        if events:
            print("\n🧠 \033[1;34mAutomatic Timeline Events Logged:\033[0m")
            for e in events:
                um.engine.log_event(e.event_type, e.summary, e.ref_id)
                print(f"  \033[32m✔\033[0m Logged event [{e.event_type}]: {e.summary}")

        # 5. Clear Superseded / Contradicted Facts
        superseded_facts = reflection.superseded_facts
        if superseded_facts:
            print("\n🧠 \033[1;31mAutomatic Contradictions Cleaned Up:\033[0m")
            from src.CoreFunctions.Infrastructure.vector_memory import delete_vector_fact as remove_vector
            for stale_fact in superseded_facts:
                remove_vector(stale_fact)
                print(f"  \033[31m✘\033[0m Superseded: \"{stale_fact}\"")

        # 6. Update Vector Memories
        vector_memories = reflection.vector_memories
        if vector_memories:
            print("\n🧠 \033[1;34mAutomatic Facts/Memories Learnt:\033[0m")
            from src.CoreFunctions.Infrastructure.vector_memory import store_vector as save_vector
            for fact in vector_memories:
                save_vector(fact.value, source=fact.source)
                print(f"  \033[32m✔\033[0m Stored: \"{fact.value}\" (Source: {fact.source})")
                
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
            from src.CoreFunctions.Infrastructure.llm_factory import get_llm
            llm = None
            local_model = os.environ.get("OLLAMA_MODEL")
            if local_model:
                try:
                    from langchain_ollama import ChatOllama
                    test_llm = ChatOllama(model=local_model, temperature=0)
                    test_llm.invoke("ping")
                    llm = test_llm
                except Exception:
                    pass
            if llm is None:
                llm = get_llm()
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
