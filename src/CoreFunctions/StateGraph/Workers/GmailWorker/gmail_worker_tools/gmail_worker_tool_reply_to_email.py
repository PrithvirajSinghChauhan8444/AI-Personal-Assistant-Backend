from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_replier import reply_to_gmail_email

def reply_to_email(message_id: str, body: str, account: str = "personal") -> str:
    """Send a reply to an existing email thread. It automatically sets thread headers (In-Reply-To, References, and Re: subject prefix).
    
    Args:
        message_id (str): The unique ID of the original email to reply to.
        body (str): The plain text body content of your reply.
        account (str): The specific account ('personal' or 'college'). Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: reply_to_email")
    try:
        return reply_to_gmail_email(message_id, body, account=account)
    except Exception as e:
        return f"Error sending reply: {e}"

gmail_worker_tool_reply_to_email = StructuredTool.from_function(
    func=reply_to_email,
    name="reply_to_email",
    description="Send a reply to an existing email thread, auto-resolving headers."
)
