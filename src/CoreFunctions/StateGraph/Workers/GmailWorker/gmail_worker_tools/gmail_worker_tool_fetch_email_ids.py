import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_ops import fetch_email_ids

def fetch_email_ids_tool(query: str, account: str = "personal") -> str:
    """Find all message IDs matching a query and return a paginated job reference.
    This creates an active job ID expiring in 30 minutes, allowing other tools to process the batch.
    
    Args:
        query (str): Gmail search query (e.g. 'is:unread', 'from:boss@company.com').
        account (str): The specific account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: fetch_email_ids")
    try:
        res = fetch_email_ids(query, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error fetching email IDs: {e}"

gmail_worker_tool_fetch_email_ids = StructuredTool.from_function(
    func=fetch_email_ids_tool,
    name="fetch_email_ids",
    description="Find all message IDs matching a query and return a job_id with count and expiration timestamp."
)
