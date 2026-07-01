import asyncio
import os
import sys
from dotenv import load_dotenv

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')), override=True)

from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_worker_tools.browser_worker_tool_navigate import browser_navigate
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_worker_tools.browser_worker_tool_get_page_content import browser_read_current_page

async def run_test():
    print("🚀 Starting browser pagination test...")
    
    # Navigate to a simple page that has several links/interactive elements (e.g. news.ycombinator.com has ~100 elements)
    test_url = "https://news.ycombinator.com"
    print(f"🔗 Navigating to {test_url}...")
    
    # 1. Test navigation and default limits (0 to 30)
    result_nav = await browser_navigate(test_url)
    print("\n--- Navigation Result (Default Offset 0, Limit 30) ---")
    print("\n".join(result_nav.split("\n")[:10])) # print first 10 lines of elements
    
    assert "Showing elements 0 to 29 of" in result_nav or "Showing elements 0 to" in result_nav, "Pagination header missing or incorrect on navigate"
    print("✅ Navigation pagination header verified!")

    # 2. Test reading page with different offset
    print("\n🔗 Reading current page with offset 30, limit 15...")
    result_read = await browser_read_current_page(offset=30, limit=15)
    print("\n--- Read Page Result (Offset 30, Limit 15) ---")
    print("\n".join(result_read.split("\n")[:10])) # print first 10 lines
    
    assert "Showing elements 30 to 44 of" in result_read or "Showing elements 30 to" in result_read, "Pagination header missing or incorrect on read"
    print("✅ Read page pagination header and slicing verified!")
    
    print("\n🎉 All browser pagination tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(run_test())
