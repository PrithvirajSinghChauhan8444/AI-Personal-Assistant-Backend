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
    from langchain_ollama import ChatOllama
except ImportError:
    print("❌ Critical: 'langchain_ollama' not installed.")
    ChatOllama = None

# ==========================================
# 1. DEFINE MEMBERS
# ==========================================
MEMBERS = [
    "GmailWorker",
    "ProductivityWorker",
    "MemoryWorker",
    "SystemWorker",
    "ClassroomWorker",
    "ObsidianWorker"
]

WORKER_INFO = {
    "GmailWorker": "Specialized in email management. Can read, search, and send emails via Gmail API.",
    "ProductivityWorker": "Manages productivity and planning. Capabilities include Calendar interactions, Google Tasks management, and checking Weather forecasts.",
    "MemoryWorker": "Handles long-term memory. Stores and recalls user preferences, facts, and context.",
    "SystemWorker": "Interfaces with the OS. Can run terminal commands, manage files, and execute scripts.",
    "ClassroomWorker": "Manages Google Classroom synchronization. Fetches active courses, coursework, assignments, and academic details.",
    "ObsidianWorker": "Local markdown note author and whiteboard/visual diagram builder. Generates interactive note files, backlinks, frontmatter, and infinite canvases (.canvas) using the Coordinate Mapping Layout Algorithm."
}

# ==========================================
# 2. DEFINE OUTPUT SCHEMA
# ==========================================
# This forces the LLM to choose ONE valid next step.
class RoutingDecision(BaseModel):
    """Result of the routing decision."""
    next: Literal["GmailWorker", "ProductivityWorker", "MemoryWorker", "SystemWorker", "ClassroomWorker", "ObsidianWorker", "FINISH"] = Field(
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
    "You are the **Orchestrator/Manager**. Your sole responsibility is to analyze requests and delegate tasks to specialized workers. "
    "You are a coordinator; you NEVER execute work or provide data yourself.\n\n"
    "### AVAILABLE WORKERS\n"
    "{worker_info}\n\n"
    "### STRICT RESTRICTIONS (MUST FOLLOW)\n"
    "1. **NO PLACEHOLDERS:** NEVER provide responses like '[list of info]' or 'Here is the data' if you haven't received it from a worker first.\n"
    "2. **Delegation Mandatory:** If a user asks for information, you MUST route to the relevant worker.\n"
    "3. **Manager Authority:** You manage the workflow. If a task is not yet done by a worker, your only valid action is to route to that worker.\n\n"
    "### OPERATIONAL WORKFLOW\n"
    "1. **Analyze History:** Look at the conversation. Has a worker already provided the requested data?\n"
    "2. **Route or Finish:** \n"
    "   - If NO: Route to the worker responsible for that data.\n"
    "   - If YES: Summarize the data received and route to 'FINISH'.\n\n"
    "### EXAMPLES\n"
    "Example 1: Routing to Worker\n"
    "Context: User asks 'What is my CPU usage?'\n"
    "Response: {{\"next\": \"SystemWorker\", \"final_response\": \"\"}}\n\n"
    "Example 2: Finishing Task\n"
    "Context: SystemWorker just reported 'CPU usage is 15%'.\n"
    "Response: {{\"next\": \"FINISH\", \"final_response\": \"Your current CPU usage is 15%.\"}}\n\n"
    "Example 3: Multi-step Progress\n"
    "Context: User wants to check email and save it. GmailWorker just provided email content.\n"
    "Response: {{\"next\": \"SystemWorker\", \"final_response\": \"\"}}"
)

formatted_system_prompt = SUPERVISOR_PROMPT.format(
    worker_info="\n".join([f"- {name}: {desc}" for name, desc in WORKER_INFO.items()])
)

# ==========================================
# 4. INITIALIZE MANAGER NODE
# ==========================================
if ChatOllama:
    llm = ChatOllama(
        model="gemma4:e4b",
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
