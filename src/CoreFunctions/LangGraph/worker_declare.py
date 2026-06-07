import os
import sys
from dotenv import load_dotenv

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

from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.systemworker import create_system_worker
from src.CoreFunctions.LangGraph.gmailworker import create_gmail_worker
from src.CoreFunctions.LangGraph.memoryworker import create_memory_worker
from src.CoreFunctions.LangGraph.productivityworker import create_productivity_worker
from src.CoreFunctions.LangGraph.classroomworker import create_classroom_worker
from src.CoreFunctions.LangGraph.obsidianworker import create_obsidian_worker
from src.CoreFunctions.LangGraph.githubworker import create_github_worker

# ==========================================
# 1. INITIALIZE MODEL
# ==========================================
if ChatOllama:
    # Using llama3 for workers as well
    llm = ChatOllama(
        model="gemma4:e4b", 
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

    # Create Classroom Worker
    worker_nodes["ClassroomWorker"] = create_classroom_worker(llm)

    # Create Obsidian Worker
    worker_nodes["ObsidianWorker"] = create_obsidian_worker(llm)
    
    # Create GitHub Worker
    worker_nodes["GithubWorker"] = create_github_worker(llm)
    
else:
    print("⚠️ Workers could not be initialized (LLM missing).")
