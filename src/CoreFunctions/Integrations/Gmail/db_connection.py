import os
import sqlite3

def get_db_connection():
    # Resolve project root and DB path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
    memory_dir = os.path.join(project_root, "Memory")
    os.makedirs(memory_dir, exist_ok=True)
    db_path = os.path.join(memory_dir, "gmail_worker.db")
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
