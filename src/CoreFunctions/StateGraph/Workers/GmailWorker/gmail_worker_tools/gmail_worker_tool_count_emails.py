import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_service import get_gmail_service

def count_emails(query: str, account: str = "personal") -> str:
    """Fetch the total count of emails matching a specific search query. Very lightweight.
    
    Args:
        query (str): Gmail search query syntax (e.g. 'is:unread', 'from:manager@company.com').
        account (str): Account name, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: count_emails")
    try:
        service = get_gmail_service(account)
        all_ids = []
        page_token = None
        
        while True:
            results = service.users().messages().list(
                userId='me',
                q=query,
                pageToken=page_token,
                fields="messages/id,nextPageToken"
            ).execute()
            
            messages = results.get('messages', [])
            all_ids.extend([m['id'] for m in messages if 'id' in m])
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        return json.dumps({
            "query": query,
            "account": account,
            "total_matching_emails": len(all_ids)
        }, indent=2)
    except Exception as e:
        return f"Error counting emails: {e}"

gmail_worker_tool_count_emails = StructuredTool.from_function(
    func=count_emails,
    name="count_emails",
    description="Fetch the total count of emails matching a specific search query without downloading contents."
)
