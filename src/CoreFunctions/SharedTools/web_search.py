import json
from langchain_core.tools import StructuredTool

def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for real-time information or questions.

    Args:
        query (str): The search term or question to query.
        max_results (int, optional): The maximum number of results to fetch. Defaults to 5.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: web_search")
    print(f"   Args: query={query}")
    
    # 1. Try Parallel Search MCP via subprocess
    try:
        import subprocess
        import uuid
        
        print("   Using Parallel Search MCP...")
        proc = subprocess.Popen(
            ["npx", "-y", "mcp-remote", "https://search.parallel.ai/mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1
        )
        try:
            # Step 1: Initialize handshake
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "python-client", "version": "1.0.0"}
                }
            }
            proc.stdin.write(json.dumps(init_req) + "\n")
            proc.stdin.flush()
            
            # Read initialize response
            init_res_line = proc.stdout.readline()
            if not init_res_line:
                raise Exception("No initialize response from MCP server")
                
            # Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            proc.stdin.write(json.dumps(initialized_notification) + "\n")
            proc.stdin.flush()
            
            # Step 2: Call web_search tool
            session_id = str(uuid.uuid4())
            call_req = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "web_search",
                    "arguments": {
                        "objective": f"Find information to answer: {query}",
                        "search_queries": [query],
                        "session_id": session_id,
                        "model_name": "gemini-2.5-pro"
                    }
                }
            }
            proc.stdin.write(json.dumps(call_req) + "\n")
            proc.stdin.flush()
            
            # Read tool call response
            call_res_line = proc.stdout.readline()
            if not call_res_line:
                raise Exception("No response from web_search tool call")
                
            res = json.loads(call_res_line)
            if "error" in res:
                raise Exception(f"MCP error: {res['error']}")
                
            # Parse output
            result = res.get("result", {})
            content = result.get("content", [])
            if not content:
                raise Exception("No content returned in MCP result")
                
            text_val = content[0].get("text", "")
            try:
                parsed_text = json.loads(text_val)
                results = parsed_text.get("results", [])
                formatted = []
                for r in results[:max_results]:
                    title = r.get("title", "No Title")
                    url = r.get("url", "")
                    excerpts = r.get("excerpts", [])
                    snippet = "\n".join(excerpts) if isinstance(excerpts, list) else str(excerpts)
                    formatted.append(f"Title: {title}\nURL: {url}\nSnippet: {snippet}\n")
                if formatted:
                    return "\n".join(formatted)[:3000]
            except Exception:
                # If not JSON, return raw text
                if text_val:
                    return text_val[:3000]
            
            raise Exception("No formatted results found in Parallel Search output")
            
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception as e:
        print(f"   ⚠️ Parallel Search MCP failed: {e}. Falling back to DuckDuckGo...")

    # 2. Fallback to DuckDuckGo search
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n")
        if not results:
            return "No search results found."
        return "\n".join(results)[:3000]
    except Exception as e:
        return f"Error executing web search: {e}"

web_search_tool = StructuredTool.from_function(
    func=web_search,
    name="web_search",
    description="Search the web for real-time information or questions."
)
