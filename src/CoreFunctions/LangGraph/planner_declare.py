import os
import sys
from dotenv import load_dotenv

# Ensure we can import from sibling modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Load env
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../config/.env'))
load_dotenv(config_path)

try:
    from langchain_groq import ChatGroq
except ImportError:
    print("❌ Critical: 'langchain_groq' not installed.")
    ChatGroq = None

from src.CoreFunctions.LangGraph.planner_define import PlannerAgent
# Reuse MEMBERS from manager_declare to ensure consistency
from src.CoreFunctions.LangGraph.manager_declare import MEMBERS, WORKER_INFO

# ==========================================
# 1. SYSTEM PROMPT
# ==========================================
PLANNER_PROMPT = (
    "You are the Planner of an advanced AI Personal Assistant system.\n"
    "Your goal is to break down the user's request into a logical sequence of steps.\n"
    "You have access to the following workers request to be performed by Manager/Supervisor:\n"
    "{worker_info}\n"
    "Each step should specify which worker (if any) is best suited for it.\n"
    "Your output will be used by the Manager to coordinate the execution.\n"
    "Be specific and tactical.\n"
    "Do not use any tools. You are only planning the steps for the Manager to execute.\n"
    "IMPORTANT: Output ONLY the step-by-step plan. Do NOT include any 'Thinking' blocks, internal monologue, or reasoning. "
    "Start directly with the plan steps."
)

# ==========================================
# 2. INITIALIZE MODEL & AGENT
# ==========================================
if ChatGroq:
    llm = ChatGroq(
        model="qwen/qwen3-32b", 
        temperature=0
    )
    
    # Format the prompt with worker info
    formatted_planner_prompt = PLANNER_PROMPT.format(
        worker_info="\n".join([f"- {name}: {desc}" for name, desc in WORKER_INFO.items()])
    )
    
    planner_agent = PlannerAgent(
        model=llm,
        members=MEMBERS,
        system_prompt=formatted_planner_prompt
    )
    
    planner_node = planner_agent.create_node()
else:
    planner_node = None
