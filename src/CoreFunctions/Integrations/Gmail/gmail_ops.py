import json
from .gmail_reader import search_gmail_emails, fetch_email_ids, read_gmail_email, get_unread_count
from .gmail_sender import send_gmail_email, create_gmail_draft, send_gmail_with_attachment
from .gmail_replier import reply_to_gmail_email
from .gmail_labels import get_or_create_label, list_gmail_labels, rename_gmail_label, delete_gmail_label
from .gmail_modifier import trash_gmail_email, mark_gmail_as_read, mark_gmail_as_unread, delete_gmail_emails_permanently, apply_label_to_emails, remove_label_from_emails
from .email_cleaner import clean_body_content

def read_gmail_msg(email_id: str, mark_read: bool = False, account: str = "personal") -> str:
    """Retrieve the full detailed plain-text body of a specific email, and optionally mark it as read."""
    try:
        res = read_gmail_email(email_id, account=account)
        if isinstance(res, dict) and "error" not in res:
            if mark_read:
                status = mark_gmail_as_read(email_id, account=account)
                res["mark_read_status"] = status
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error reading email: {e}"

def fetch_unread_mails(mode: str = "list", limit: int = 5, page_token: str = None, account: str = "personal") -> str:
    """Fetches unread email information (counts or lists) from specified Gmail account(s)."""
    limit = min(max(1, limit), 10)
    try:
        if mode == "count":
            if account == "both":
                return json.dumps({
                    "personal": get_unread_count("personal"),
                    "college": get_unread_count("college")
                }, indent=2)
            else:
                return json.dumps(get_unread_count(account), indent=2)
        
        # Default/Fallback to "list" mode
        if account == "both":
            res_personal = search_gmail_emails("is:unread", limit, page_token=page_token, account="personal")
            res_college = search_gmail_emails("is:unread", limit, page_token=page_token, account="college")
            return json.dumps({
                "personal": res_personal,
                "college": res_college
            }, indent=2)
        else:
            res = search_gmail_emails("is:unread", limit, page_token=page_token, account=account)
            return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error fetching mails: {e}"
