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
# ==========================================
# 1. DEFINE MEMBERS
# ==========================================
# These must match the names of the nodes we will create in the graph.
MEMBERS = [
    "GmailWorker",
    "ProductivityWorker",
    "MemoryWorker",
    "SystemWorker",
    "WhatsAppWorker"
]

WORKER_INFO = {
    "GmailWorker": "Specialized in email management. Can read, search, and send emails via Gmail API.",
    "ProductivityWorker": "Manages productivity and planning. Capabilities include Calendar interactions, Google Tasks management, and checking Weather forecasts.",
    "MemoryWorker": "Handles long-term memory. Stores and recalls user preferences, facts, and context.",
    "SystemWorker": "Interfaces with the OS. Can run terminal commands, manage files, and execute scripts.",
    "WhatsAppWorker": "Handles WhatsApp messaging. Manages server/session connection and sends messages."
}

# ==========================================
# 2. SYSTEM PROMPT
# ==========================================
SUPERVISOR_PROMPT = (
    "You are the Supervisor (Manager) of an advanced AI Personal Assistant system.\n"
    "Your role is to coordinate the following workers, each with specific capabilities:\n"
    "{worker_info}\n"
    "1. Receive the user's request.\n"
    "2. Analyze which worker is best suited to handle the next step based on their capabilities.\n"
    "3. Route the conversation to that worker.\n"
    "4. If the task is fully completed or requires user input that you don't have, route to FINISH.\n"
    "5. Do NOT try to answer the query yourself if it involves tools. Delegate it.\n"
    "6. If the task is fully completed:\n"
    "   - You MUST output the 'FINISH' signal.\n"
    "   - You MUST wrap your friendly closing message inside the 'final_response' field of your output schema.\n"
    "   - DO NOT write raw text outside of the JSON/Schema structure.\n"
    "7. If the user just says 'hello' or chatty things, behave like a helpful assistant and route to FINISH, "
    "but MUST provide a friendly 'final_response' in your output.\n"
    "8. **Tool Chaining**: You can chain multiple workers to complete a complex task. "
    "The output of one worker is added to the conversation history and is visible to the next worker. "
    "You do not need to manually pass data; just route effectively.\n"
    
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
    
    # Format the prompt with worker info
    formatted_system_prompt = SUPERVISOR_PROMPT.format(
        worker_info="\n".join([f"- {name}: {desc}" for name, desc in WORKER_INFO.items()])
    )
    
    manager_agent = ManagerAgent(
        model=llm,
        members=MEMBERS,
        system_prompt=formatted_system_prompt
    )
    
    # This is the callable node for the graph
    manager_node = manager_agent.create_node()
else:
    manager_node = None
