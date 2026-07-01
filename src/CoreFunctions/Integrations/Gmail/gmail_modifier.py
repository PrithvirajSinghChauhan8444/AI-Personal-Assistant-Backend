from .gmail_service import get_gmail_service
from .gmail_labels import get_or_create_label

def trash_gmail_email(email_id: str, account: str = "personal") -> str:
    """Move a specific email message to the Trash folder."""
    try:
        service = get_gmail_service(account)
        service.users().messages().trash(userId='me', id=email_id).execute()
        return f"Successfully moved email {email_id} to Trash on account '{account}'."
    except Exception as e:
        return f"Error trashing email: {e}"

def mark_gmail_as_read(email_id: str, account: str = "personal") -> str:
    """Mark an email message as read by removing the UNREAD label."""
    try:
        service = get_gmail_service(account)
        service.users().messages().batchModify(
            userId='me',
            body={
                'ids': [email_id],
                'removeLabelIds': ['UNREAD']
            }
        ).execute()
        return f"Successfully marked email {email_id} as read on account '{account}'."
    except Exception as e:
        return f"Error marking email as read: {e}"

def mark_gmail_as_unread(email_id: str, account: str = "personal") -> str:
    """Mark an email message as unread by adding the UNREAD label."""
    try:
        service = get_gmail_service(account)
        service.users().messages().batchModify(
            userId='me',
            body={
                'ids': [email_id],
                'addLabelIds': ['UNREAD']
            }
        ).execute()
        return f"Successfully marked email {email_id} as unread on account '{account}'."
    except Exception as e:
        return f"Error marking email as unread: {e}"

def delete_gmail_emails_permanently(message_ids: list, account: str = "personal") -> str:
    """Permanently delete a list of emails (bypassing Trash). Requires confirmed=True in tool layer."""
    try:
        service = get_gmail_service(account)
        service.users().messages().batchDelete(
            userId='me',
            body={
                'ids': message_ids
            }
        ).execute()
        return f"Successfully deleted {len(message_ids)} email(s) permanently."
    except Exception as e:
        raise Exception(f"Failed to permanently delete emails: {e}")

def apply_label_to_emails(label_name: str, message_ids: list, account: str = "personal") -> str:
    """Applies a label to a list of messages."""
    try:
        service = get_gmail_service(account)
        label_id = get_or_create_label(service, label_name, account)
        service.users().messages().batchModify(
            userId='me',
            body={
                'ids': message_ids,
                'addLabelIds': [label_id]
            }
        ).execute()
        return f"Successfully applied label '{label_name}' to {len(message_ids)} email(s)."
    except Exception as e:
        raise Exception(f"Failed to apply label: {e}")

def remove_label_from_emails(label_name: str, message_ids: list, account: str = "personal") -> str:
    """Removes a label from a list of messages."""
    try:
        service = get_gmail_service(account)
        label_id = get_or_create_label(service, label_name, account)
        service.users().messages().batchModify(
            userId='me',
            body={
                'ids': message_ids,
                'removeLabelIds': [label_id]
            }
        ).execute()
        return f"Successfully removed label '{label_name}' from {len(message_ids)} email(s)."
    except Exception as e:
        raise Exception(f"Failed to remove label: {e}")
