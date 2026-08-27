import json
from datetime import datetime
from .db_connection import get_db_connection

def init_db():
    conn = get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_cache (
                email_id TEXT PRIMARY KEY,
                account TEXT,
                subject TEXT,
                sender TEXT,
                to_address TEXT,
                date TEXT,
                body TEXT,
                thread_id TEXT,
                attachments TEXT,              -- JSON string representation
                cached_at TEXT                 -- ISO 8601 string representation
            )
        """)
        conn.commit()
    finally:
        conn.close()

# Auto-initialize table on import
init_db()

def get_cached_email(email_id: str, account: str) -> dict | None:
    """Retrieve raw email cached data, resolving JSON attachments list."""
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "SELECT subject, sender, to_address, date, body, thread_id, attachments FROM email_cache WHERE email_id = ? AND account = ?",
            (email_id, account)
        )
        row = cursor.fetchone()
        if row:
            subject, sender, to_address, date, body, thread_id, attachments_raw = row
            try:
                attachments = json.loads(attachments_raw) if attachments_raw else []
            except Exception:
                attachments = []
            return {
                "id": email_id,
                "subject": subject,
                "sender": sender,
                "to": to_address,
                "date": date,
                "body": body,
                "threadId": thread_id,
                "attachments": attachments
            }
        return None
    finally:
        conn.close()

def cache_email(email_id: str, account: str, email_data: dict):
    """Insert or replace an email record in SQLite cache with ISO timestamp."""
    conn = get_db_connection()
    try:
        attachments_raw = json.dumps(email_data.get("attachments", []))
        conn.execute(
            """
            INSERT OR REPLACE INTO email_cache 
            (email_id, account, subject, sender, to_address, date, body, thread_id, attachments, cached_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email_id,
                account,
                email_data.get("subject", ""),
                email_data.get("sender", ""),
                email_data.get("to", ""),
                email_data.get("date", ""),
                email_data.get("body", ""),
                email_data.get("threadId", ""),
                attachments_raw,
                datetime.now().isoformat()
            )
        )
        conn.commit()
    finally:
        conn.close()

def clear_email_cache(email_id: str = None):
    """Deletes cached emails globally or by specific ID."""
    conn = get_db_connection()
    try:
        if email_id:
            conn.execute("DELETE FROM email_cache WHERE email_id = ?", (email_id,))
        else:
            conn.execute("DELETE FROM email_cache")
        conn.commit()
    finally:
        conn.close()
