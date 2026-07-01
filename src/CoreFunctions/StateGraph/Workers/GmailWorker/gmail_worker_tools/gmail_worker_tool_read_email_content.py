import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_ops import read_gmail_email

def read_email_content(message_id: str, account: str = "personal") -> str:
    """Fetch and return cleaned content (subject, sender, date, cleaned body, attachments metadata) of a single email.
    The body is cleaned of script tags, base64 images, style sheets, tracking pixels, and truncated to 2000 characters to prevent context window overload.
    
    Args:
        message_id (str): The unique message/email ID.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: read_email_content")
    try:
        res = read_gmail_email(message_id, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error reading email content: {e}"

gmail_worker_tool_read_email_content = StructuredTool.from_function(
    func=read_email_content,
    name="read_email_content",
    description="Fetch and return cleaned content (subject, sender, date, body, attachments) of a single email."
)
