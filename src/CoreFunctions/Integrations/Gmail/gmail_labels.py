import json
from .gmail_service import get_gmail_service
from .label_cache import get_cached_label_id, cache_label_id, invalidate_label_cache

def get_or_create_label(service, name: str, account: str) -> str:
    """Returns label ID by name, checking cache first, creating it if it doesn't exist."""
    # Check SQLite cache first
    cached_id = get_cached_label_id(name, account)
    if cached_id:
        return cached_id
        
    # Not in cache, query Google API
    try:
        labels = service.users().labels().list(userId='me').execute().get('labels', [])
        for label in labels:
            if label['name'].lower() == name.lower():
                label_id = label['id']
                cache_label_id(name, account, label_id)
                return label_id
                
        # Create label if not found
        created = service.users().labels().create(
            userId='me', body={"name": name}
        ).execute()
        label_id = created['id']
        cache_label_id(name, account, label_id)
        return label_id
    except Exception as e:
        print(f"Error in get_or_create_label for {account}: {e}")
        raise e

def list_gmail_labels(account: str = "personal") -> dict:
    """List all available labels in the mailbox."""
    try:
        service = get_gmail_service(account)
        results = service.users().labels().list(userId='me').execute()
        return results
    except Exception as e:
        raise Exception(f"Failed to list labels: {e}")

def rename_gmail_label(old_name: str, new_name: str, account: str = "personal") -> dict:
    """Rename a custom/user label and update local cache."""
    try:
        service = get_gmail_service(account)
        labels = service.users().labels().list(userId='me').execute().get('labels', [])
        label_id = None
        for label in labels:
            if label['name'].lower() == old_name.lower():
                label_id = label['id']
                break
                
        if not label_id:
            raise Exception(f"Label '{old_name}' not found.")
            
        updated = service.users().labels().patch(
            userId='me', id=label_id, body={"name": new_name}
        ).execute()
        
        # Invalidate old cache and cache the new one
        invalidate_label_cache(account, old_name)
        cache_label_id(new_name, account, label_id)
        
        return updated
    except Exception as e:
        raise Exception(f"Failed to rename label: {e}")

def delete_gmail_label(label_name: str, account: str = "personal") -> str:
    """Delete a custom/user label by name and invalidate from cache."""
    try:
        service = get_gmail_service(account)
        labels = service.users().labels().list(userId='me').execute().get('labels', [])
        label_id = None
        for label in labels:
            if label['name'].lower() == label_name.lower():
                label_id = label['id']
                break
                
        if not label_id:
            raise Exception(f"Label '{label_name}' not found.")
            
        service.users().labels().delete(userId='me', id=label_id).execute()
        invalidate_label_cache(account, label_name)
        return f"Successfully deleted label '{label_name}' on account '{account}'."
    except Exception as e:
        raise Exception(f"Failed to delete label: {e}")
