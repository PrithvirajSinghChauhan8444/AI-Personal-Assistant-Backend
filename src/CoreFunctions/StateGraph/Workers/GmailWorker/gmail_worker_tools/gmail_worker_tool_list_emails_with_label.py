import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_ops import search_gmail_emails

def list_emails_with_label(label_name: str, max_results: int = 10, account: str = "personal") -> str:
    """List emails that have a specific label applied, returning metadata (sender, subject, date, snippet).
    
    Args:
        label_name (str): The name of the label to filter by.
        max_results (int): Max matches to return. Defaults to 10.
        account (str): The specific account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: list_emails_with_label")
    try:
        # Construct label query e.g. label:"label_name"
        query = f'label:"{label_name}"'
        res = search_gmail_emails(query, max_results=max_results, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error listing emails with label: {e}"

gmail_worker_tool_list_emails_with_label = StructuredTool.from_function(
    func=list_emails_with_label,
    name="list_emails_with_label",
    description="List emails that have a specific label applied, returning metadata."
)
