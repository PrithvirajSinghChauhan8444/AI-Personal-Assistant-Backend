import os
import sys
from dotenv import load_dotenv

# Ensure we can import from sibling modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Load env from config/.env
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../config/.env'))
load_dotenv(config_path)

try:
    from langchain_groq import ChatGroq
except ImportError:
    print("❌ Critical: 'langchain_groq' not installed. Please install it.")
    ChatGroq = None

from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import system_control_tools

# ==========================================
# 1. INITIALIZE MODEL
# ==========================================
if ChatGroq:
    # Using the same model as Manager for consistency, or as specialized.
    # Qwen 2.5 32b is good for tool use.
    llm = ChatGroq(
        model="qwen/qwen-2.5-32b", 
        temperature=0
    )
else:
    llm = None

# ==========================================
# 2. DEFINE SYSTEM WORKER
# ==========================================

system_prompt = (
    "You are the SystemWorker. "
    "Your capabilities include running terminal commands, python scripts, and launching applications. "
    "You should use the available tools to fulfill the user's request. "
    "If you have completed the action, simply state what you did."
)

worker_nodes = {}

if llm:
    system_worker = WorkerAgent(
        model=llm,
        tools=system_control_tools,
        system_prompt=system_prompt
    )
    
    # The key implementation details:
    # The node name MUST match the name in MEMBERS list in manager_declare.py
    worker_nodes["SystemWorker"] = system_worker.create_node()
else:
    print("⚠️ SystemWorker could not be initialized (LLM missing).")
