import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_service import get_gmail_service
from src.CoreFunctions.Integrations.Gmail.label_cache import invalidate_label_cache, cache_label_id

def rename_label(old_name: str, new_name: str, account: str = "personal") -> str:
    """Rename a custom/user label. This updates the local label cache.
    
    Args:
        old_name (str): The current name of the label.
        new_name (str): The new name to assign to the label.
        account (str): The specific account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: rename_label")
    try:
        service = get_gmail_service(account)
        # Find the label ID of the old label name
        labels = service.users().labels().list(userId='me').execute().get('labels', [])
        label_id = None
        for label in labels:
            if label['name'].lower() == old_name.lower():
                label_id = label['id']
                break
                
        if not label_id:
            return f"Error: Label '{old_name}' not found."
            
        body = {
            "name": new_name
        }
        
        updated_label = service.users().labels().patch(userId='me', id=label_id, body=body).execute()
        
        # Invalidate old cache entry and cache the new one
        invalidate_label_cache(account, old_name)
        cache_label_id(new_name, account, label_id)
        
        return json.dumps({
            "status": "success",
            "label_id": label_id,
            "old_name": old_name,
            "new_name": new_name
        }, indent=2)
    except Exception as e:
        return f"Error renaming label: {e}"

gmail_worker_tool_rename_label = StructuredTool.from_function(
    func=rename_label,
    name="rename_label",
    description="Rename a custom/user label in Gmail."
)
