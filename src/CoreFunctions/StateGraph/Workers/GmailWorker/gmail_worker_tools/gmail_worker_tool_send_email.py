from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_sender import send_gmail_email

def send_email(to: str, subject: str, body: str, account: str = "personal") -> str:
    """Create and send an email message.
    
    Args:
        to (str): The recipient's email address.
        subject (str): The subject line of the email.
        body (str): The plain text body content.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: send_email")
    try:
        return send_gmail_email(to, subject, body, account=account)
    except Exception as e:
        return f"Error sending email: {e}"

gmail_worker_tool_send_email = StructuredTool.from_function(
    func=send_email,
    name="send_email",
    description="Create and send an email message."
)
