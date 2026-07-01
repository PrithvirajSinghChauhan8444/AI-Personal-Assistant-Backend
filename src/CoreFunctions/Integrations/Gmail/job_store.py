import json
import uuid
from datetime import datetime, timedelta
from .db_connection import get_db_connection

def init_db():
    conn = get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_jobs (
                job_id TEXT PRIMARY KEY,
                query TEXT,
                all_ids TEXT,                  -- JSON serialized list of message IDs
                total_matching_emails INTEGER,
                expires_at TEXT,               -- ISO 8601 string
                status TEXT,                   -- 'active' | 'expired'
                account TEXT                   -- 'personal' | 'college'
            )
        """)
        conn.commit()
    finally:
        conn.close()

# Auto-initialize table on import
init_db()

def create_email_job(query: str, ids: list, account: str) -> dict:
    job_id = "job_" + uuid.uuid4().hex[:8]
    expires_at = (datetime.now() + timedelta(minutes=30)).isoformat()
    all_ids_str = json.dumps(ids)
    total_matching_emails = len(ids)
    
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO email_jobs (job_id, query, all_ids, total_matching_emails, expires_at, status, account)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, query, all_ids_str, total_matching_emails, expires_at, "active", account)
        )
        conn.commit()
    finally:
        conn.close()
        
    return {
        "job_id": job_id,
        "query": query,
        "total_matching_emails": total_matching_emails,
        "expires_at": expires_at
    }

def get_job_info(job_id: str) -> tuple:
    """Returns (ids, query, account, is_expired) for a job."""
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT all_ids, query, account, expires_at, status FROM email_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None
        all_ids_str, query, account, expires_at_str, status = row
        expires_at = datetime.fromisoformat(expires_at_str)
        is_expired = datetime.now() > expires_at or status == "expired"
        return json.loads(all_ids_str), query, account, is_expired
    finally:
        conn.close()
