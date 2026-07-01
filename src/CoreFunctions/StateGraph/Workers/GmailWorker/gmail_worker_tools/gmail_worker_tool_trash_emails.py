import json
from typing import List
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_service import get_gmail_service
from src.CoreFunctions.Integrations.Gmail.job_store import get_job_info

def trash_emails(
    job_id: str = None, 
    message_ids: List[str] = None, 
    offset: int = 0, 
    limit: int = 20, 
    account: str = "personal"
) -> str:
    """Move a batch of emails to the Trash folder.
    Provide either a `job_id` (with optional offset/limit) or a specific list of `message_ids`.
    
    Args:
        job_id (str, optional): The job ID returned from fetch_email_ids.
        message_ids (list, optional): List of specific email IDs to move to trash.
        offset (int, optional): Slicing offset if using a job_id. Defaults to 0.
        limit (int, optional): Slicing limit if using a job_id. Defaults to 20.
        account (str, optional): Target account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: trash_emails")
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
            return json.dumps({"status": "no matching emails to trash", "count": 0}, indent=2)

        service = get_gmail_service(target_account)
        trashed_ids = []
        for msg_id in target_ids:
            service.users().messages().trash(userId='me', id=msg_id).execute()
            trashed_ids.append(msg_id)

        return json.dumps({
            "status": "success",
            "count": len(trashed_ids),
            "trashed_ids": trashed_ids
        }, indent=2)

    except Exception as e:
        return f"Error moving emails to trash: {e}"

gmail_worker_tool_trash_emails = StructuredTool.from_function(
    func=trash_emails,
    name="trash_emails",
    description="Move a batch of emails to the Trash folder."
)
