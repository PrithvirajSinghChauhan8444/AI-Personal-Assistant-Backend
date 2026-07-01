import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_service import get_gmail_service
from src.CoreFunctions.Integrations.Gmail.gmail_ops import get_or_create_label

def create_label(name: str, account: str = "personal") -> str:
    """Create a new custom label in Gmail or return its ID if it already exists.
    
    Args:
        name (str): The name of the label (e.g. 'Job Applications').
        account (str): The specific account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: create_label")
    try:
        service = get_gmail_service(account)
        label_id = get_or_create_label(service, name, account)
        return json.dumps({"status": "success", "name": name, "label_id": label_id}, indent=2)
    except Exception as e:
        return f"Error creating label: {e}"

gmail_worker_tool_create_label = StructuredTool.from_function(
    func=create_label,
    name="create_label",
    description="Create a new label in Gmail or get its ID if it exists."
)
