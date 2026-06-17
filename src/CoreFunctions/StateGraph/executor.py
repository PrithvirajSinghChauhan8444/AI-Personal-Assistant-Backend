import os
import sys
import json
import re
import asyncio
from typing import List, Literal, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

from src.CoreFunctions.StateGraph.state import AgentState
from src.CoreFunctions.tools import HumanInterventionAbortError, HumanInterventionReplanError
from src.CoreFunctions.StateGraph.registry import WorkerRegistry

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

AGENT_MAP = {}
_model_cache = {}

def get_model_for_worker(worker_name: str):
    global _model_cache
    if worker_name in _model_cache:
        return _model_cache[worker_name]
        
    if not hasattr(WorkerRegistry, "_config") or not WorkerRegistry._config:
        WorkerRegistry.load_and_sync_config()
        
    worker_config = WorkerRegistry._config.get(worker_name, {})
    model_name = worker_config.get("model")
    
    if not model_name:
        try:
            worker = WorkerRegistry.get_worker(worker_name)
            use_local = worker.use_local_llm
        except KeyError:
            use_local = worker_name in ["MemoryWorker", "ObsidianNoteWorker", "ObsidianCanvasWorker", "ObsidianRefactorWorker"]
        model_name = os.environ.get("OLLAMA_MODEL", "gemma4:e4b") if use_local else os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
        
    if "gemini" in model_name.lower():
        llm_kwargs = {}
        llm_kwargs["extra_body"] = {"thinking_config": {"thinking_budget": 2048}}
        model = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            model_kwargs=llm_kwargs
        )
    else:
        model = ChatOllama(
            model=model_name,
            temperature=0,
            options={"thinking": True}
        )
        
    _model_cache[worker_name] = model
    return model

def compile_worker_agents():
    """Compiles react agents dynamically for all registered workers."""
    global AGENT_MAP
    for name, worker in WorkerRegistry.get_all_workers().items():
        if not worker.tools and not worker.instructions:
            continue
        model = get_model_for_worker(name)
        prompt = worker.instructions + THINKING_INSTRUCTION + HUMAN_INTERVENTION_INSTRUCTION
        AGENT_MAP[name] = create_react_agent(model, worker.tools, prompt=prompt)
    
    # Legacy fallback mapping
    if "BrowserNavigator" in AGENT_MAP:
        AGENT_MAP["BrowserWorker"] = AGENT_MAP["BrowserNavigator"]

def _get_active_task(state: AgentState, worker_name: str):
    """Finds the task currently marked 'in_progress' and assigned to the given worker"""
    for task in state.get("active_subtasks", []):
        if task["status"] == "in_progress" and task["assigned_worker"] == worker_name:
            return task
    return None

def _load_worker_skills(worker_name: str) -> str:
    """Dynamically loads and formats procedural skills matching the categories assigned to a worker using the skills index cache."""
    from src.CoreFunctions.vector_memory import _load_skills_data
    
    try:
        categories = WorkerRegistry.get_worker(worker_name).categories
    except KeyError:
        categories = [worker_name]
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
    if "user_profile" in working_memory:
        cleaned["user_profile"] = working_memory["user_profile"]
    
    if depends_on is not None:
        for dep in depends_on:
            if dep in working_memory:
                cleaned[dep] = working_memory[dep]
    else:
        system_keys = {"active_skills", "skills_index", "previous_session_summary", "user_profile", "relevant_memories", "fast_path_matched"}
        for k, v in working_memory.items():
            if k not in system_keys:
                cleaned[k] = v
    return cleaned

def _run_ephemeral_agent(worker_name: str, task_desc: str, working_memory: dict, depends_on: list = None):
    """Runs a pre-compiled ReAct agent in complete isolation, returning only the final answer."""
    from src.CoreFunctions.logger import log_worker_start, log_worker_thought, log_worker_tool_call, log_worker_tool_response, log_worker_end
    
    # Ensure compile has run at least once
    if not AGENT_MAP:
        compile_worker_agents()
        
    agent = AGENT_MAP[worker_name]
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
    try:
        if not hasattr(WorkerRegistry, "_config") or not WorkerRegistry._config:
            WorkerRegistry.load_and_sync_config()
        model_name = WorkerRegistry._config.get(worker_name, {}).get("model")
    except Exception:
        model_name = None
        
    if not model_name:
        try:
            worker = WorkerRegistry.get_worker(worker_name)
            use_local = worker.use_local_llm
        except KeyError:
            use_local = worker_name in ["MemoryWorker", "ObsidianNoteWorker", "ObsidianCanvasWorker", "ObsidianRefactorWorker"]
        model_name = os.environ.get("OLLAMA_MODEL", "gemma4:e4b") if use_local else os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    log_worker_start(worker_name, task_desc, model_name, prompt)

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
        for chunk in agent.stream({"messages": [HumanMessage(content=prompt)]}):
            for node_name, node_update in chunk.items():
                messages = node_update.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
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
                    
                    elif msg.type == "tool":
                        print(f"  📥 [{worker_name}] Tool \033[1;32m{msg.name}\033[0m successfully returned response.")
                        log_worker_tool_response(worker_name, msg.name, getattr(msg, "content", ""))
                    
                    if msg.type == "ai":
                        last_ai_message = msg
        
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
    
    # Ensure compile has run at least once
    if not AGENT_MAP:
        compile_worker_agents()
        
    agent = AGENT_MAP[worker_name]
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
    try:
        if not hasattr(WorkerRegistry, "_config") or not WorkerRegistry._config:
            WorkerRegistry.load_and_sync_config()
        model_name = WorkerRegistry._config.get(worker_name, {}).get("model")
    except Exception:
        model_name = None
        
    if not model_name:
        try:
            worker = WorkerRegistry.get_worker(worker_name)
            use_local = worker.use_local_llm
        except KeyError:
            use_local = worker_name in ["MemoryWorker", "ObsidianNoteWorker", "ObsidianCanvasWorker", "ObsidianRefactorWorker"]
        model_name = os.environ.get("OLLAMA_MODEL", "gemma4:e4b") if use_local else os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    log_worker_start(worker_name, task_desc, model_name, prompt)

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
        async for chunk in agent.astream({"messages": [HumanMessage(content=prompt)]}):
            for node_name, node_update in chunk.items():
                messages = node_update.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
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
                    
                    elif msg.type == "tool":
                        print(f"  📥 [{worker_name}] Tool \033[1;32m{msg.name}\033[0m successfully returned response.")
                        log_worker_tool_call(worker_name, msg.name, getattr(msg, "content", ""))
                    
                    if msg.type == "ai":
                        last_ai_message = msg
        
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
    updated_subtask = None
    for st in subtasks:
        if st["id"] == task_id:
            st["status"] = "completed"
            updated_subtask = st
            break
    
    working_memory = state.get("working_memory", {})
    
    try:
        from src.CoreFunctions.unified_memory import UnifiedMemory
        um = UnifiedMemory()
        
        clean_summary = final_data
        has_entities = False
        
        if isinstance(final_data, str):
            extracted = UnifiedMemory.extract_entities(final_data)
            clean_summary = extracted["summary"]
            has_entities = bool(extracted.get("extracted_entities"))
        elif isinstance(final_data, dict):
            has_entities = bool(final_data.get("extracted_entities"))
            clean_summary = final_data.get("summary", final_data)

        if um.enabled:
            if has_entities:
                um.store_memory(task_id, final_data, sharable=True, persistent=True)
                print(f"  ⚡ [UnifiedMemory] Shareable entities found. Storing '{task_id}' in workspace cache.")
            else:
                print(f"  ℹ️ [UnifiedMemory] Skipping store of transient output for '{task_id}' (no shareable tags found).")
        
        final_data = clean_summary
    except Exception as um_err:
        print(f"  ⚠️ [UnifiedMemory] Failed to evaluate/write output to cache: {um_err}")

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
        "active_subtasks": [updated_subtask] if updated_subtask else [],
        "working_memory": working_memory,
        "completed_tasks": completed_tasks
    }

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
    except HumanInterventionAbortError as ex:
        print(f"  🛑 [{worker_name}] Task aborted by user request.")
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
        log_node_end(worker_name, output_state)
        return output_state
    except HumanInterventionReplanError as ex:
        print(f"  🔄 [{worker_name}] Re-routing back to Task Router for re-planning.")
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
        log_node_end(worker_name, output_state)
        return output_state
    except Exception as ex:
        print(f"  ❌ [{worker_name}] Task {task['id']} failed: {ex}")
        log_error(worker_name, str(ex))
        subtasks = state.get("active_subtasks", [])
        for st in subtasks:
            if st["id"] == task["id"]:
                st["status"] = "failed"
        new_error = f"Worker {worker_name} failed on task {task['id']}: {ex}"
        output_state = {
            "active_subtasks": subtasks,
            "error_logs": [new_error]
        }
        log_node_end(worker_name, output_state)
        return output_state
