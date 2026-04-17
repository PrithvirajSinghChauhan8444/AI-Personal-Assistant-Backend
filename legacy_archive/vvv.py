# ===== Standard Library =====
import os
import sys
import json
import re
import inspect

# ===== Third Party =====
import google.generativeai as genai
from dotenv import load_dotenv

# ===== Path Fix =====
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ===== Internal Imports =====
from CoreFunctions.tools import AVAILABLE_TOOLS
from CoreFunctions.memory import fetch_memory

# ===== Models =====
PLANNER_MODEL = "gemma-3-27b-it"
EXECUTOR_MODEL = "gemma-3-12b-it"

# ===== ENV =====
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY missing")
genai.configure(api_key=api_key)

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def is_question(text: str) -> bool:
    t = text.lower().strip()
    return (
        t.endswith("?")
        or t.startswith(("what", "who", "where", "when", "why", "how"))
        or "tell me" in t
        or "do you know" in t
    )

def is_user_fact(text: str) -> bool:
    t = text.lower()
    return any(
        p in t
        for p in [
            "my name is",
            "i am ",
            "my email is",
            "my phone is",
            "i live in",
            "i prefer",
        ]
    )

def classify_intent(text: str) -> str:
    if is_question(text):
        return "question"
    if is_user_fact(text):
        return "fact"
    if any(v in text.lower() for v in ["send", "mail", "email", "find", "get", "check", "play", "open"]):
        return "command"
    return "mixed"

def normalize_tool_calls(code: str) -> str:
    """
    Converts tool-style calls like:
      get_weather.get_weather(x) → get_weather(x)
      send_mail.send_mail(x)     → send_mail(x)
    """

    for tool_name in AVAILABLE_TOOLS.keys():
        pattern = rf"{tool_name}\.{tool_name}\s*\("
        replacement = f"{tool_name}("
        code = re.sub(pattern, replacement, code)

    return code


def normalize_tool_arguments(code: str) -> str:
    """
    Normalizes ONLY positional arguments based on tool signatures.
    - NEVER removes keyword arguments
    - Removes positional args only if tool takes zero params
    """

    for tool_name, fn in AVAILABLE_TOOLS.items():
        sig = inspect.signature(fn)

        # Count total parameters (positional + keyword)
        params = sig.parameters

        # Regex to match tool calls
        pattern = rf"{tool_name}\s*\((.*?)\)"

        def repl(match):
            arg_str = match.group(1).strip()

            if not arg_str:
                return f"{tool_name}()"

            # Split args safely
            args = [a.strip() for a in arg_str.split(",") if a.strip()]

            positional_args = []
            keyword_args = []

            for a in args:
                if "=" in a:
                    keyword_args.append(a)
                else:
                    positional_args.append(a)

            # If function takes no parameters at all → drop ALL args
            if len(params) == 0:
                return f"{tool_name}()"

            # Otherwise:
            # - Keep ALL keyword args
            # - Keep positional args as-is (or trim if needed later)
            final_args = positional_args + keyword_args

            return f"{tool_name}({', '.join(final_args)})"

        code = re.sub(pattern, repl, code)

    return code









# --------------------------------------------------
# JSON CLEANER
# --------------------------------------------------
def clean_json_string(text):
    text = re.sub(r"```json|```", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1]

# --------------------------------------------------
# MEMORY PLACEHOLDER RESOLUTION
# --------------------------------------------------
def resolve_memory_placeholders(text):
    pattern = r"\[recall\s+([a-zA-Z0-9_\-]+)\]"

    def repl(match):
        key = match.group(1)
        value = fetch_memory(None, key)  # smart lookup
        return value if value else f"[missing {key}]"

    return re.sub(pattern, repl, text)

# --------------------------------------------------
# PLANNER
# --------------------------------------------------
def plan_tasks(user_input):
    model = genai.GenerativeModel(PLANNER_MODEL)
    # tool_list = list(AVAILABLE_TOOLS.keys())
    # Generate rich tool info with signatures and docstrings
    tool_info_lines = []
    for name, func in AVAILABLE_TOOLS.items():
        sig = inspect.signature(func)
        doc = (func.__doc__ or "").strip().split("\n")[0]
        tool_info_lines.append(f"{name}{sig}: {doc}")
    tool_info = "\n".join(tool_info_lines)

    prompt = f"""
User request:
{user_input}

Available tools (Function Signatures):
{tool_info}

Return JSON ONLY:
{{
  "tasks": [
    {{ "tool": "<tool_name>", "input": "<string or dict>" }}
  ]
}}

RULES:
-Tools are FUNCTIONS.
-Call them directly: get_weather("Agra")
-NEVER use tool.tool() syntax.
- For simple conversations like: hello hi ,just reply accordingly no tool execution needed
- recall(key) takes ONLY a key, never categories
- NEVER use recall("user") or recall("past")
- remember is ONLY for new information
- NEVER remember questions
- ONLY call the tools exactly as listed
- NEVER call a tool with empty or missing arguments
- If input is missing, use the original user input value
- NEVER write import statements
- NEVER reference tools as modules
- Tools are FUNCTIONS, not modules
- Call tools directly like: get_weather("Agra")
- INVALID: import get_weather, get_weather.get_weather(...),from tools import get_weather
- For communication tools (WhatsApp, Email), if the user's message content is vague (e.g. "send something", "say hi"), generate a friendly, context-appropriate message.
- Do NOT use the user's command description as the message body. e.g. "Tell him I am late" -> message="I am late", NOT "Tell him I am late".
"""

    response = model.generate_content(prompt)
    return json.loads(clean_json_string(response.text)).get("tasks", [])













# --------------------------------------------------
# PLAN VALIDATOR
# --------------------------------------------------
def validate_and_fix_plan(tasks, user_input):
    validated = []

    for task in tasks:
        tool = task.get("tool")
        inp = task.get("input")

        if tool not in AVAILABLE_TOOLS:
            continue

        if tool == "recall" and isinstance(inp, str):
            if inp.lower() in ("user", "past", "current"):
                continue

        if tool == "remember":
            if is_question(user_input):
                continue
            if isinstance(inp, dict):
                if is_question(inp.get("value", "")):
                    continue

        validated.append(task)

    return validated

# --------------------------------------------------
# EXECUTOR
# --------------------------------------------------
def process_command(user_input, history=None):
    result=None
    script_path=None

    def divider(title):
        print("\n" + "=" * 20 + f" {title} " + "=" * 20)

    divider("USER INPUT")
    print(user_input)

    intent = classify_intent(user_input)
    print("Detected intent:", intent)

    # -------- FAST PATH FOR QUESTIONS --------
    if intent == "question":
        resolved = resolve_memory_placeholders(user_input)
        if "[missing" not in resolved:
            divider("FINAL RESPONSE")
            print(resolved)
            return resolved

    divider("PLANNING")
    raw_tasks = plan_tasks(user_input)
    tasks = validate_and_fix_plan(raw_tasks, user_input)
    print(json.dumps(tasks, indent=2))






    print("🧠 Running in AGENT MODE")

    model = genai.GenerativeModel(EXECUTOR_MODEL)
    chat = model.start_chat(history=history or [])

    observations = []

    for step, task in enumerate(tasks, start=1):
        divider(f"STEP {step}")

        tool_name = task.get("tool")
        raw_input = task.get("input")

        print("Tool:", tool_name)
        print("Raw input:", raw_input)

        func = AVAILABLE_TOOLS.get(tool_name)
        if not func:
            continue

        # -------- REMEMBER --------
        if tool_name == "remember":
            if isinstance(raw_input, dict):
                key = raw_input.get("key")
                value = raw_input.get("value")
                category = raw_input.get("category", "past")
                if not key or not value or is_question(value):
                    continue
            else:
                key = raw_input
                if observations:
                    value = observations[-1].split(":", 1)[-1].strip()
                    category = "past"
                elif is_user_fact(user_input):
                    value = user_input
                    category = "user"
                else:
                    continue

            args = {"key": key, "value": value, "category": category}
            print("Auto-mapped remember args:", args)
            result = func(**args)
            observations.append(f"remember: {result}")
            continue

        # -------- RESOLVE MEMORY --------
        if isinstance(raw_input, dict):
            for k, v in raw_input.items():
                if isinstance(v, str):
                    raw_input[k] = resolve_memory_placeholders(v)

        # -------- ARG MAPPING --------
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        if isinstance(raw_input, dict):
            args = raw_input
        elif isinstance(raw_input, str) and len(params) >= 1:
            # Map string to the first parameter
            args = {params[0]: raw_input}
        else:
            args = {}

        if any(p not in args and sig.parameters[p].default is inspect._empty for p in params):
            missing = [p for p in params if p not in args and sig.parameters[p].default is inspect._empty]
            print(f"⚠️ SKIPPING Tool {tool_name}: Missing required arguments: {missing}")
            continue

        result = func(**args)
        print("Tool output:", result)

        observations.append(f"{tool_name}: {result}")
        chat.send_message(f"OBSERVATION: {result}")

    divider("FINAL RESPONSE")

    final_prompt = f"""
User request:
{user_input}

Observations:
{observations}

Write a clear final response.
No explanations.
"""

    response = chat.send_message(final_prompt)
    final_answer = response.text.strip()
    print(final_answer)
    return final_answer

# ENTRY
# --------------------------------------------------
if __name__ == "__main__":
    print("🤖 AI Personal Assistant V2 (vvv.py) - Secured & Offline Capable")
    print("Type 'exit' to quit.\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ("exit", "quit"):
                print("👋 Goodbye!")
                break
            
            if not user_input:
                continue
                
            process_command(user_input)
            print("\n" + "-"*40 + "\n")
            
        except KeyboardInterrupt:
            print("\n❌ Interrupted.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
