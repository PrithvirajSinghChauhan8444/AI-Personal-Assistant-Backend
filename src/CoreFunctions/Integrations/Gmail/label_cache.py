from datetime import datetime
from .db_connection import get_db_connection

def init_db():
    conn = get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS label_cache (
                name TEXT,
                account TEXT,                  -- 'personal' | 'college'
                label_id TEXT,
                cached_at TEXT,                -- ISO 8601 string
                PRIMARY KEY (name, account)
            )
        """)
        conn.commit()
    finally:
        conn.close()

# Auto-initialize table on import
init_db()

def get_cached_label_id(name: str, account: str) -> str:
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT label_id FROM label_cache WHERE name = ? AND account = ?", (name, account))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()

def cache_label_id(name: str, account: str, label_id: str):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO label_cache (name, account, label_id, cached_at) VALUES (?, ?, ?, ?)",
            (name, account, label_id, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()

def invalidate_label_cache(account: str, name: str = None):
    conn = get_db_connection()
    try:
        if name:
            conn.execute("DELETE FROM label_cache WHERE name = ? AND account = ?", (name, account))
        else:
            conn.execute("DELETE FROM label_cache WHERE account = ?", (account,))
        conn.commit()
    finally:
        conn.close()
