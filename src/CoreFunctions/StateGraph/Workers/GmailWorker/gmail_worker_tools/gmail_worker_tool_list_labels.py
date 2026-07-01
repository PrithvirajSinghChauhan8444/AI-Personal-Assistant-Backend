import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_service import get_gmail_service

def list_labels(account: str = "personal") -> str:
    """List all available labels (system and custom/user labels) in the mailbox.
    
    Args:
        account (str): The specific account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: list_labels")
    try:
        service = get_gmail_service(account)
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        return json.dumps({"labels": labels}, indent=2)
    except Exception as e:
        return f"Error listing labels: {e}"

gmail_worker_tool_list_labels = StructuredTool.from_function(
    func=list_labels,
    name="list_labels",
    description="List all available labels in the mailbox."
)
