import os
import sys
from dotenv import load_dotenv
from typing import Literal, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from src.CoreFunctions.LangGraph.logger import GraphLogger

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

# ==========================================
# 1. DEFINE MEMBERS
# ==========================================
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
# 2. DEFINE OUTPUT SCHEMA
# ==========================================
# This forces the LLM to choose ONE valid next step.
class RoutingDecision(BaseModel):
    """Result of the routing decision."""
    next: Literal["GmailWorker", "ProductivityWorker", "MemoryWorker", "SystemWorker", "WhatsAppWorker", "FINISH"] = Field(
        description="The specific worker to route to, or 'FINISH' if the task is complete."
    )
    final_response: Optional[str] = Field(
        description="A friendly response to the user. Required if routing to FINISH. Keep it empty otherwise."
    )

# ==========================================
# 3. SYSTEM PROMPT
# ==========================================
SUPERVISOR_PROMPT = (
    "### ROLE & IDENTITY\n"
    "You are the **Orchestrator/Manager**. Your sole responsibility is to analyze requests and delegate tasks. "
    "You are the master decision-maker; you do not execute the work yourself.\n\n"
    "### AVAILABLE WORKERS\n"
    "{worker_info}\n\n"
    "### STRICT RESTRICTIONS (MUST FOLLOW)\n"
    "1. **Closed Worker Set:** You must **ONLY** select from the specifically provided list of workers above. "
    "**NEVER** assume the existence of, hallucinate, or route to a worker that is not explicitly defined in your registry.\n"
    "2. **Delegation Only:** You are **strictly prohibited** from calling tools or executing functions yourself. "
    "Do not attempt to answer the query directly if it requires a tool. Your job is only to select the correct worker and let them handle the task.\n"
    "3. **Manager Authority:** You manage the workflow. If a task requires action, route it. "
    "If a task requires multiple steps, route to the first logical worker (Worker Chaining).\n\n"
    "### OPERATIONAL WORKFLOW\n"
    "1. **Receive & Analyze:** Receive the user's request. Analyze which worker from the **available list** is best suited to handle the immediate next step based on their defined capabilities.\n"
    "2. **Route:** Route the conversation to that selected worker.\n"
    "   - *Note on Chaining:* The output of one worker is added to the history for the next. You do not need to manually pass data; just route effectively.\n"
    "3. **Finish Condition:** If (and ONLY if) the task is fully completed or requires user input that you do not have:\n"
    "   - You **MUST** output the 'FINISH' signal.\n"
    "   - You **MUST** wrap your friendly closing message inside the `final_response` field of your output schema.\n"
    "   - **DO NOT** write raw text outside of the JSON/Schema structure.\n"
    "4. **Chitchat Handling:** If the user just says 'hello' or chatty things that require no worker action, "
    "behave like a helpful assistant and route to FINISH, providing a friendly `final_response`."
)

formatted_system_prompt = SUPERVISOR_PROMPT.format(
    worker_info="\n".join([f"- {name}: {desc}" for name, desc in WORKER_INFO.items()])
)

# ==========================================
# 4. INITIALIZE MANAGER NODE
# ==========================================
if ChatGroq:
    llm = ChatGroq(
        model="qwen/qwen3-32b",
        temperature=0
    )
    
    # Bind the schema to the LLM
    structured_llm = llm.with_structured_output(RoutingDecision)

    def manager_node(state: dict):
        GraphLogger.log_node_start("Manager")
        
        messages = state.get("messages", [])
        
        # Run the LLM with structured output
        decision = structured_llm.invoke([SystemMessage(content=formatted_system_prompt)] + messages)
        
        GraphLogger.log_decision("Manager", decision.next, details=f"Final Response: {'Yes' if decision.final_response else 'No'}")
        GraphLogger.log_node_end("Manager")
        
        return {
            "next": decision.next,
            "final_response": decision.final_response
        }

else:
    manager_node = None
