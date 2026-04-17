import os
import sys
from dotenv import load_dotenv

# Ensure we can import from sibling modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Load env
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../config/.env'))
load_dotenv(config_path)

try:
    from langchain_ollama import ChatOllama
except ImportError:
    print("❌ Critical: 'langchain_ollama' not installed.")
    ChatOllama = None

from src.CoreFunctions.LangGraph.planner_define import PlannerAgent
# Reuse MEMBERS from manager_declare to ensure consistency
from src.CoreFunctions.LangGraph.manager_declare import MEMBERS, WORKER_INFO

# ==========================================
# 1. SYSTEM PROMPT
# ==========================================
PLANNER_PROMPT = (
    "You are the Planner. Create a direct, technical plan for the Manager.\n"
    "Available workers:\n"
    "{worker_info}\n\n"
    "### RULES\n"
    "1. Keep it simple. One worker per step.\n"
    "2. Be technical. Specify exactly what tool the worker should use if possible.\n"
    "3. DO NOT hallucinate work. Only plan for what the user asked.\n"
    "4. Output ONLY the numbered list of steps.\n\n"
    "### EXAMPLES\n"
    "User: 'Check my RAM usage and email it to boss@company.com'\n"
    "Plan:\n"
    "1. SystemWorker: get_system_stats (RAM)\n"
    "2. GmailWorker: send_mail (recipient='boss@company.com', body='RAM Stats...')\n\n"
    "User: 'Search my emails for flight tickets and save the details to travel.txt'\n"
    "Plan:\n"
    "1. GmailWorker: search_emails (query='flight ticket')\n"
    "2. SystemWorker: write_file (filename='travel.txt', content='...') \n\n"
    "User: 'What is the weather in London?'\n"
    "Plan:\n"
    "1. ProductivityWorker: get_weather (location='London')"
)

# ==========================================
# 2. INITIALIZE MODEL & AGENT
# ==========================================
if ChatOllama:
    llm = ChatOllama(
        model="gemma4:e4b", 
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
