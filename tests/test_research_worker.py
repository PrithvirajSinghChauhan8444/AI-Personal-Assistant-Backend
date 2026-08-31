import sys
import os

# Ensure src path is in Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.StateGraph.worker_framework import WorkerRegistry, scan_and_register_workers
from src.CoreFunctions.SharedTools.web_search import web_search_tool

def test_research_worker_registration():
    print("🔬 Scanning and registering workers...")
    scan_and_register_workers(force_reload=True)
    
    print("🔬 Verifying ResearchWorker registration...")
    workers = WorkerRegistry.get_all_workers()
    assert "ResearchWorker" in workers, "ResearchWorker is not registered!"
    
    worker = WorkerRegistry.get_worker("ResearchWorker")
    print(f"  Worker Name: {worker.name}")
    print(f"  Worker Description: {worker.description}")
    
    # Verify tools
    tool_names = [t.name for t in worker.tools]
    print(f"  Worker Tools: {tool_names}")
    assert "web_search" in tool_names, "web_search tool is missing from ResearchWorker!"
    assert "browser_read_page_content" in tool_names, "browser_read_page_content is missing from ResearchWorker!"
    
    # Verify instructions
    assert "ResearchWorker" in worker.instructions, "ResearchWorker prompt is misconfigured!"
    print("  ✅ Registration and structure test passed.")

def test_web_search_dynamic_limits():
    print("\n🔍 Testing web_search tool dynamic limits...")
    # Verify the signature accepts max_length
    import inspect
    sig = inspect.signature(web_search_tool.func)
    print(f"  web_search signature: {sig}")
    assert "max_length" in sig.parameters, "max_length parameter is missing from web_search signature!"
    
    # Run a test query with a custom max_length
    res = web_search_tool.func(query="AI research news", max_results=2, max_length=150)
    print(f"  Search result preview (max_length=150):\n{res}")
    assert len(res) <= 155, f"Returned text exceeded maximum length limit! Length: {len(res)}"
    print("  ✅ Dynamic limits test passed.")

def test_research_modes_prompt_isolation():
    print("\n🔬 Testing ResearchWorker dynamic prompt isolation...")
    worker = WorkerRegistry.get_worker("ResearchWorker")
    
    # 1. Deep research query
    deep_task = "Perform deep research and prepare a comprehensive report on quantum computing breakthroughs."
    deep_prompt = worker.get_task_instruction(deep_task)
    assert "DEEP RESEARCH MODE" in deep_prompt, "Deep research prompt not returned for deep research task!"
    assert "NORMAL RESEARCH MODE" not in deep_prompt, "Normal research prompt leaked into deep research mode!"
    assert "deep_research" in deep_prompt, "deep_research tool instruction missing from deep research prompt!"
    assert "arXiv" in deep_prompt, "Target sources (e.g. arXiv) missing from deep research prompt!"
    assert "Mandatory Source Attribution" in deep_prompt, "Source attribution missing from deep research prompt!"
    print("  ✅ Deep research prompt isolation verified.")
    
    # 2. Normal / small research query
    normal_task = "What is the current stock price of Apple and latest headline?"
    normal_prompt = worker.get_task_instruction(normal_task)
    assert "NORMAL RESEARCH MODE" in normal_prompt, "Normal research prompt not returned for normal research task!"
    assert "DEEP RESEARCH MODE" not in normal_prompt, "Deep research prompt leaked into normal research mode!"
    assert "STRICT PROHIBITION - NO BROWSER" in normal_prompt, "No-browser rule missing from normal research prompt!"
    assert "web_search" in normal_prompt, "web_search instruction missing from normal research prompt!"
    print("  ✅ Normal research prompt isolation verified.")

if __name__ == "__main__":
    print("=== Starting ResearchWorker Tests ===")
    test_research_worker_registration()
    test_research_modes_prompt_isolation()
    test_web_search_dynamic_limits()
    print("\n=== All ResearchWorker Tests Passed ===")

