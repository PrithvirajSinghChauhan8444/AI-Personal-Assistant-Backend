import json
from typing import List
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_service import get_gmail_service
from src.CoreFunctions.Integrations.Gmail.gmail_ops import get_or_create_label
from src.CoreFunctions.Integrations.Gmail.job_store import get_job_info

def remove_label_from_emails(
    label_name: str, 
    job_id: str = None, 
    message_ids: List[str] = None, 
    offset: int = 0, 
    limit: int = 20, 
    account: str = "personal"
) -> str:
    """Remove a specific custom label from a batch of emails.
    Provide either a `job_id` (with optional offset/limit) or a specific list of `message_ids`.
    
    Args:
        label_name (str): The name of the label to remove.
        job_id (str, optional): The job ID returned from fetch_email_ids.
        message_ids (list, optional): List of specific email IDs to unlabel.
        offset (int, optional): Slicing offset if using a job_id. Defaults to 0.
        limit (int, optional): Slicing limit if using a job_id. Defaults to 20.
        account (str, optional): Target account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: remove_label_from_emails")
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
            target_ids = ids[offset : offset + limit]
        elif message_ids:
            target_ids = message_ids
        else:
            return "Error: Must specify either 'job_id' or a list of 'message_ids'."

        if not target_ids:
            return json.dumps({"status": "no matching emails to update", "count": 0}, indent=2)

        service = get_gmail_service(target_account)
        label_id = get_or_create_label(service, label_name, target_account)

        service.users().messages().batchModify(
            userId='me',
            body={
                'ids': target_ids,
                'removeLabelIds': [label_id]
            }
        ).execute()

        return json.dumps({
            "status": "success",
            "count": len(target_ids),
            "removed_label": label_name,
            "label_id": label_id,
            "updated_ids": target_ids
        }, indent=2)

    except Exception as e:
        return f"Error removing label from emails: {e}"

gmail_worker_tool_remove_label_from_emails = StructuredTool.from_function(
    func=remove_label_from_emails,
    name="remove_label_from_emails",
    description="Remove a specific custom label from a batch of emails."
)
