import json
from langchain_core.tools import tool
from modules.workers.communication_worker.integrations.gmail_client import (
    search_emails,
    read_email,
    send_email,
    create_draft,
    reply_email
)

@tool
def fetch_unread_emails(max_count: int = 5, account: str = "personal") -> str:
    """Fetches list of unread emails with sender, subject, date, and snippet from Gmail account ('personal' or 'college')."""
    try:
        data = search_emails(query="is:unread", max_results=max_count, account=account)
        emails = data.get("emails", [])
        if not emails:
            return f"No unread emails found on '{account}' account."

        lines = [f"Found {len(emails)} unread emails on '{account}' account:"]
        for idx, em in enumerate(emails, 1):
            sender = em.get("sender", "Unknown sender")
            subject = str(em.get("subject", "No subject")).replace("<email_subject>", "").replace("</email_subject>", "")
            date = em.get("date", "")
            snippet = str(em.get("snippet", "")).replace("<email_snippet>", "").replace("</email_snippet>", "")
            lines.append(f"{idx}. ID: {em.get('id', '')} | From: {sender} | Date: {date}\n   Subject: {subject}\n   Preview: {snippet}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching unread emails from Gmail: {e}"

@tool
def send_email_tool(recipient: str, subject: str, body: str, account: str = "personal") -> str:
    """Sends an email message via Gmail client."""
    try:
        return str(send_email(to=recipient, subject=subject, body=body, account=account))
    except Exception as e:
        return f"Error sending email: {e}"

@tool
def read_email_tool(message_id: str, account: str = "personal") -> str:
    """Reads full content and details of a single email by its message ID."""
    try:
        res = read_email(message_id=message_id, account=account)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error reading email {message_id}: {e}"

@tool
def create_draft_tool(recipient: str, subject: str, body: str, account: str = "personal") -> str:
    """Creates a draft email in the user's Gmail mailbox."""
    try:
        return str(create_draft(to=recipient, subject=subject, body=body, account=account))
    except Exception as e:
        return f"Error creating draft: {e}"

@tool
def reply_email_tool(message_id: str, body: str, reply_all: bool = False, account: str = "personal") -> str:
    """Replies to an existing email thread."""
    try:
        return str(reply_email(message_id=message_id, body=body, reply_all=reply_all, account=account))
    except Exception as e:
        return f"Error replying to email: {e}"

gmail_tools = [fetch_unread_emails, send_email_tool, read_email_tool, create_draft_tool, reply_email_tool]
