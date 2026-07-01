import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_service import get_gmail_service
from src.CoreFunctions.Integrations.Gmail.label_cache import invalidate_label_cache

def delete_label(label_name: str, account: str = "personal") -> str:
    """Delete a custom/user label from Gmail by its name. This also invalidates the local label cache.
    
    Args:
        label_name (str): The exact name of the label to delete.
        account (str): The specific account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: delete_label")
    try:
        service = get_gmail_service(account)
        # Find the label ID by name from the API list to delete it
        labels = service.users().labels().list(userId='me').execute().get('labels', [])
        label_id = None
        for label in labels:
            if label['name'].lower() == label_name.lower():
                label_id = label['id']
                break
                
        if not label_id:
            return f"Error: Label '{label_name}' not found."
            
        service.users().labels().delete(userId='me', id=label_id).execute()
        # Invalidate the cache
        invalidate_label_cache(account, label_name)
        
        return json.dumps({"status": "success", "deleted_label": label_name, "label_id": label_id}, indent=2)
    except Exception as e:
        return f"Error deleting label: {e}"

gmail_worker_tool_delete_label = StructuredTool.from_function(
    func=delete_label,
    name="delete_label",
    description="Delete a custom/user label from Gmail by its name."
)
