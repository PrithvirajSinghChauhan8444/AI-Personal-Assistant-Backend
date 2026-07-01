import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_ops import read_gmail_email, mark_gmail_as_read

def process_email(message_id: str, account: str = "personal") -> str:
    """Read a single email's content and automatically mark it as read in one operation.
    Use this when you need to process a specific email and ensure it is marked read.
    
    Args:
        message_id (str): The unique message/email ID.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: process_email")
    try:
        # Read the email content
        res = read_gmail_email(message_id, account=account)
        if isinstance(res, dict) and "error" not in res:
            # Mark it read
            status = mark_gmail_as_read(message_id, account=account)
            res["marked_read"] = True
            res["mark_read_status"] = status
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error processing email: {e}"

gmail_worker_tool_process_email = StructuredTool.from_function(
    func=process_email,
    name="process_email",
    description="Read a single email's content and automatically mark it as read."
)
