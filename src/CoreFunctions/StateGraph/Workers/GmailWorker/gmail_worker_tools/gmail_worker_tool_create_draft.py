from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_sender import create_gmail_draft

def create_draft(to: str, subject: str, body: str, account: str = "personal") -> str:
    """Create a draft email in the user's mailbox.
    
    Args:
        to (str): The recipient's email address.
        subject (str): The subject line of the draft.
        body (str): The plain text body content.
        account (str): The target Google account, either 'personal' or 'college'. Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: create_draft")
    try:
        return create_gmail_draft(to, subject, body, account=account)
    except Exception as e:
        return f"Error creating draft: {e}"

gmail_worker_tool_create_draft = StructuredTool.from_function(
    func=create_draft,
    name="create_draft",
    description="Create a draft email in the user's mailbox."
)
