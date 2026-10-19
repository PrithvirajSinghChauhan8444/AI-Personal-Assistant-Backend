from langchain_core.tools import tool

@tool
def fetch_unread_emails(max_count: int = 5) -> str:
    """Fetches list of unread emails with sender and subject snippet."""
    # Isolated tool logic with mock or actual backend hook
    return f"Found 2 unread emails:\n1. From: support@github.com, Subject: Security Alert\n2. From: newsletter@tech.com, Subject: Daily Digest"

@tool
def send_email_tool(recipient: str, subject: str, body: str) -> str:
    """Sends an email message to a specified recipient."""
    return f"Email successfully dispatched to '{recipient}' with subject '{subject}'."

gmail_tools = [fetch_unread_emails, send_email_tool]
