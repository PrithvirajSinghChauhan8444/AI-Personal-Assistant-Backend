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

if __name__ == "__main__":
    print("=== Starting ResearchWorker Tests ===")
    test_research_worker_registration()
    test_web_search_dynamic_limits()
    print("\n=== All ResearchWorker Tests Passed ===")
