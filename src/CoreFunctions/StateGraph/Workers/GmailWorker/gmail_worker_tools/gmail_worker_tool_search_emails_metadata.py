import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_ops import search_gmail_emails

def search_emails_metadata(query: str, max_results: int = 10, account: str = "personal") -> str:
    """Search for emails matching a query and return metadata only (sender, subject, date, snippet). No full body.
    
    Args:
        query (str): Gmail query syntax (e.g. 'from:example@gmail.com', 'subject:meeting').
        max_results (int): Max matches to return. Defaults to 10.
        account (str): The specific account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: search_emails_metadata")
    try:
        res = search_gmail_emails(query, max_results=max_results, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error searching emails metadata: {e}"

gmail_worker_tool_search_emails_metadata = StructuredTool.from_function(
    func=search_emails_metadata,
    name="search_emails_metadata",
    description="Search for emails matching a query and return metadata (sender, subject, date, snippet) only."
)
