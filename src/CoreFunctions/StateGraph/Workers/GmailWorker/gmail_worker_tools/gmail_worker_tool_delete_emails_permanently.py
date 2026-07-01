import json
from typing import List
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_service import get_gmail_service
from src.CoreFunctions.Integrations.Gmail.job_store import get_job_info

def delete_emails_permanently(
    job_id: str = None, 
    message_ids: List[str] = None, 
    confirmed: bool = False, 
    account: str = "personal"
) -> str:
    """Permanently delete a batch of emails. This bypasses the Trash folder and cannot be undone.
    WARNING: Set 'confirmed' to True only if the human user has explicitly approved this deletion.
    
    Args:
        job_id (str, optional): The job ID returned from fetch_email_ids.
        message_ids (list, optional): List of specific email IDs to permanently delete.
        confirmed (bool): Confirmation gate flag. Must be explicitly True. Defaults to False.
        account (str, optional): Target account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: delete_emails_permanently")
    if not confirmed:
        return "❌ Error: This is a permanent, destructive operation. You must request explicit confirmation from the human user first, then call this tool with confirmed=True."

    target_ids = []
    target_account = account

    try:
        if job_id:
            job_data = get_job_info(job_id)
            if not job_data:
                return f"Error: Job ID '{job_id}' not found."
            ids, query, job_acc, is_expired = job_data
            if is_expired:
                return f"Error: Job ID '{job_id}' has expired. Please run a new fetch first."
            target_account = job_acc
            target_ids = ids
        elif message_ids:
            target_ids = message_ids
        else:
            return "Error: Must specify either 'job_id' or a list of 'message_ids'."

        if not target_ids:
            return json.dumps({"status": "no matching emails to delete", "count": 0}, indent=2)

        service = get_gmail_service(target_account)
        deleted_ids = []
        for msg_id in target_ids:
            service.users().messages().delete(userId='me', id=msg_id).execute()
            deleted_ids.append(msg_id)

        return json.dumps({
            "status": "success",
            "count": len(deleted_ids),
            "permanently_deleted_ids": deleted_ids
        }, indent=2)

    except Exception as e:
        return f"Error permanently deleting emails: {e}"

gmail_worker_tool_delete_emails_permanently = StructuredTool.from_function(
    func=delete_emails_permanently,
    name="delete_emails_permanently",
    description="Permanently delete a batch of emails. Requires confirmed=True."
)
