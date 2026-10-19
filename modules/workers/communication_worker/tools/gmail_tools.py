import json
from langchain_core.tools import tool

@tool
def fetch_unread_emails(max_count: int = 5, account: str = "personal") -> str:
    """Fetches list of unread emails with sender, subject, date, and snippet from real Gmail account ('personal' or 'college')."""
    try:
        from src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_worker_tools.gmail_worker_tool_search_emails_metadata import search_emails_metadata
        res = search_emails_metadata(query="is:unread", max_results=max_count, account=account)
        if isinstance(res, str):
            try:
                data = json.loads(res)
            except Exception:
                return res
        else:
            data = res

        emails = data.get("emails", [])
        if not emails:
            return f"No unread emails found on '{account}' account."

        lines = [f"Found {len(emails)} unread emails on '{account}' account:"]
        for idx, em in enumerate(emails, 1):
            sender = em.get("sender", "Unknown sender")
            subject = em.get("subject", "No subject").replace("<email_subject>", "").replace("</email_subject>", "")
            date = em.get("date", "")
            snippet = em.get("snippet", "").replace("<email_snippet>", "").replace("</email_snippet>", "")
            lines.append(f"{idx}. From: {sender} | Date: {date}\n   Subject: {subject}\n   Preview: {snippet}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching unread emails from Gmail: {e}"

@tool
def send_email_tool(recipient: str, subject: str, body: str, account: str = "personal") -> str:
    """Sends an email message via real Gmail client."""
    try:
        from src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_worker_tools.gmail_worker_tool_send_email import send_email
        return str(send_email(to=recipient, subject=subject, body=body, account=account))
    except Exception as e:
        return f"Error sending email: {e}"

gmail_tools = [fetch_unread_emails, send_email_tool]
