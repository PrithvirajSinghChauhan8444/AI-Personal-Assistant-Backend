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
from src.CoreFunctions.LangGraph.systemworker import create_system_worker
from src.CoreFunctions.LangGraph.gmailworker import create_gmail_worker
from src.CoreFunctions.LangGraph.memoryworker import create_memory_worker
from src.CoreFunctions.LangGraph.productivityworker import create_productivity_worker

# ==========================================
# 1. INITIALIZE MODEL
# ==========================================
if ChatGroq:
    # Using the same model as Manager for consistency, or as specialized.
    # Qwen 2.5 32b is good for tool use.
    llm = ChatGroq(
        model="qwen/qwen3-32b", 
        temperature=0
    )
else:
    llm = None

# ==========================================
# 2. DEFINE WORKERS
# ==========================================

worker_nodes = {}

if llm:
    # Create System Worker
    worker_nodes["SystemWorker"] = create_system_worker(llm)
    
    # Create Gmail Worker
    worker_nodes["GmailWorker"] = create_gmail_worker(llm)

    # Create Memory Worker
    worker_nodes["MemoryWorker"] = create_memory_worker(llm)

    # Create Productivity Worker (Replaces CalendarWorker)
    worker_nodes["ProductivityWorker"] = create_productivity_worker(llm)
    
else:
    print("⚠️ Workers could not be initialized (LLM missing).")
