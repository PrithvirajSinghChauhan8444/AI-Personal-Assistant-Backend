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
    # Fallback or strict error if missing
    print("❌ Critical: 'langchain_groq' not installed. Please install it.")
    ChatGroq = None

from src.CoreFunctions.LangGraph.manager_define import ManagerAgent


# ==========================================
# 1. DEFINE MEMBERS
# ==========================================
# These must match the names of the nodes we will create in the graph.
MEMBERS = [
    "GmailWorker",
    "CalendarWorker",
    "ProductivityWorker",  # Tasks, Notes
    "FileWorker",          # File Ops
    "SystemWorker",        # Terminal, App Launching
    "WhatsAppWorker"       # WhatsApp Ops
]

# ==========================================
# 2. SYSTEM PROMPT
# ==========================================
SUPERVISOR_PROMPT = (
    "You are the Supervisor (Manager) of an advanced AI Personal Assistant system.\n"
    "Your role is to coordinate the following workers: {members}.\n"
    "1. Receive the user's request.\n"
    "2. Analyze which worker is best suited to handle the next step.\n"
    "3. Route the conversation to that worker.\n"
    "4. If the task is fully completed or requires user input that you don't have, route to FINISH.\n"
    "5. Do NOT try to answer the query yourself if it involves tools. Delegate it.\n"
    "6. If the user just says 'hello' or chatty things, behave like a helpful assistant and route to FINISH, "
    "but MUST provide a friendly 'final_response' in your output.\n"
)

# ==========================================
# 3. INITIALIZE MODEL & AGENT
# ==========================================
# User requested: qwen/qwen3-32b from Groq
# Note: Ensure GROQ_API_KEY is in .env

if ChatGroq:
    llm = ChatGroq(
        model="qwen/qwen3-32b", # Exact model string as requested
        temperature=0
    )
    
    manager_agent = ManagerAgent(
        model=llm,
        members=MEMBERS,
        system_prompt=SUPERVISOR_PROMPT
    )
    
    # This is the callable node for the graph
    manager_node = manager_agent.create_node()
else:
    manager_node = None
