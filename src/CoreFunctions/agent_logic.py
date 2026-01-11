import sys
import os
import json
import inspect
import logging
import warnings
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv

# ==========================================
# 🔧 PATH FIX (MUST BE AT THE VERY TOP)
# ==========================================
# Ensures the script finds 'CoreFunctions' when run from different subdirectories
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- SUPPRESS DEPRECATION WARNINGS ---
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai
from CoreFunctions.tools import AVAILABLE_TOOLS

# ==========================================
# 🔧 INITIALIZATION & STRUCTURED LOGGING
# ==========================================
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ ERROR: GEMINI_API_KEY not found in .env file.")
else:
    genai.configure(api_key=api_key)

LOG_FILE_JSON = 'jarvis_execution_logs.json'

def log_event(message, response=None, extra_data=None, step=None):
    """
    Logs structured JSON with function tracking and token counts.
    Includes 'step' parameter to track specific iterations in the ReAct loop.
    """
    # Use inspect to find the function that invoked this log
    caller = inspect.stack()[1].function
    
    log_entry = {
        "timestamp": datetime.now().isoformat(), # ISO-8601 formatting for logs
        "function": caller,
        "step": f"Loop Step {step}" if step else "N/A",
        "message": message,
        "tokens": {},
        "extra": extra_data or {}
    }
    
    # Extract token usage if response is available
    if response and hasattr(response, 'usage_metadata'):
        u = response.usage_metadata
        log_entry["tokens"] = {
            "in": u.prompt_token_count, 
            "out": u.candidates_token_count, 
            "total": u.total_token_count
        }
    
    with open(LOG_FILE_JSON, "a") as f:
        f.write(json.dumps(log_entry) + "\n") # Structured JSON logging
    
    # Console Feedback
    step_prefix = f"[Step {step}] " if step else ""
    print(f"📊 {step_prefix}[{caller}] {message}")

# ==========================================
# 🔍 PHASE 1: DISPATCHER (Discovery)
# ==========================================
def discover_tools_and_data(user_input):
    model = genai.GenerativeModel('gemma-3-12b-it')
    tool_index = "\n".join([f"- {k}: {v.__doc__}" for k, v in AVAILABLE_TOOLS.items()])
    
    prompt = f"""
    Analyze the user request and identify necessary tools and logic.
    TOOLS AVAILABLE: {tool_index}
    INPUT: {user_input}
    OUTPUT JSON ONLY: {{'intent': str, 'needed': list, 'data': dict, 'plan': list}}
    """
    
    response = model.generate_content(prompt)
    log_event("Discovery completed", response) # Logs the intent discovery phase
    raw = response.text.strip().replace("```json", "").replace("```", "")
    return json.loads(raw)

# ==========================================
# 🧠 PHASE 2: BRAIN (ReAct Loop)
# ==========================================
def process_command(user_input, history=None):
    """
    Accepts user text and optional history payload.
    Logs every tool call with arguments and loop progression.
    """
    discovery = discover_tools_and_data(user_input)
    needed = discovery.get('needed', [])
    selected_schemas = {k: AVAILABLE_TOOLS[k].__doc__ for k in needed if k in AVAILABLE_TOOLS}
    completed_actions = []

    model = genai.GenerativeModel(model_name='gemma-3-12b-it')
    chat_session = model.start_chat(history=history if history else [])

    # ReAct Execution Loop (1 to 10 steps)
    for step in range(1, 11):
        log_event(f"Initializing ReAct Loop iteration", step=step)
        
        instruction = f"DATA: {discovery.get('data')}\nTASK: Execute logical step."
        response = chat_session.send_message(instruction)
        
        # Log response metadata and token cost for this step
        log_event(f"Brain responded", response=response, step=step)
        
        raw_text = response.text.strip().replace("```json", "").replace("```", "")
        try:
            decision = json.loads(raw_text)
        except json.JSONDecodeError:
            log_event("JSON Decode Error", step=step, extra_data={"raw": raw_text})
            return "Internal logic error: Invalid JSON generated."

        # Final Response Handling
        if "response" in decision:
            log_event("Final result generated", step=step, extra_data={"res": decision["response"]})
            return decision["response"]

        # Tool Execution & Argument Logging
        if "tool" in decision:
            t_name = decision["tool"]
            t_args = decision.get("args", {})
            func = AVAILABLE_TOOLS.get(t_name)
            
            # CRITICAL: Logs exactly which tool is called and with what arguments
            log_event(f"TOOL CALL: {t_name}", step=step, extra_data={"args": t_args})
            
            if func:
                result = func(**t_args)
                completed_actions.append(f"Used {t_name}")
                chat_session.send_message(f"OBSERVATION: {result}")
            else:
                log_event(f"Tool {t_name} not found", step=step)
                chat_session.send_message(f"ERROR: Tool '{t_name}' not found.")

    return "Task reached max complexity."

if __name__ == "__main__":
    test_cmd = """Hey Jarvis, do a quick status check for me. I want to know how the system is holding up and what time it is, and also grab the current weather in Agra. While you're at it, see if you can find that 'work_context' note I saved earlier.

Check my inbox too. If there's anything urgent or project-related—or if you notice the laptop battery is getting low—go ahead and add a high-priority reminder to my task list to look into it. Also, let me know what my schedule looks like for the rest of the day.

If the weather back home looks like rain, let's block out three hours tomorrow morning starting at 10 AM for some deep work. If it’s actually a nice day, just make a note in my memory that it's a good day for working outside.

Finally, send a quick update to prithvi24101@iiitnr.edu.in. Just tell him the diagnostics are done, include the health stats, and let him know the assistant is officially up and running. Once that's all set, put on some music that fits the current vibe and the weather"""
    print(f"\n🤖 FINAL: {process_command(test_cmd)}")