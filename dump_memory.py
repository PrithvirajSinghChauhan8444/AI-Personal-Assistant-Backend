import os
import sys
import json
import sqlite3
import time
from dotenv import load_dotenv

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Load .env
load_dotenv(override=True)

from src.CoreFunctions.Infrastructure.MemoryLayer import MemoryManager
from src.CoreFunctions.Infrastructure.vector_memory import _load_data as _load_vector_data

def dump_memory():
    print("=" * 60)
    print("📋 Unified Memory System Current Contents")
    print("=" * 60)

    now = time.time()
    um = MemoryManager()
    print(f"\n⚙️  Active Cache Provider: {um.engine.__class__.__name__}")
    
    key_values = {}
    
    # 1. Inspect Active Engine (Redis / SQLite / Postgres)
    if um.enabled:
        try:
            active_keys = um.list_keys("*")
            for k in active_keys:
                payload = um.retrieve_memory(k)
                if payload:
                    key_values[k] = (payload, False) # (payload, is_expired)
        except Exception as e:
            print(f"⚠️ Error reading active structured memory engine: {e}")

    # 2. Inspect local SQLite cache DB directly (to include raw / expired cache entries)
    sqlite_db_path = os.path.abspath("Memory/workspace_cache.db")
    if os.path.exists(sqlite_db_path):
        try:
            conn = sqlite3.connect(sqlite_db_path)
            cursor = conn.execute("SELECT key, value, expires_at FROM cache")
            for row in cursor.fetchall():
                key, val_str, expires_at = row[0], row[1], row[2]
                is_expired = expires_at < now
                if key not in key_values:
                    try:
                        parsed = json.loads(val_str)
                    except Exception:
                        parsed = val_str
                    key_values[key] = (parsed, is_expired)
            conn.close()
        except Exception as e:
            pass

    print("\n--- Structured Memory Keys (SQLite / Redis / Postgres) ---")
    if not key_values:
        print("No structured keys found in the database.")
    else:
        by_category = {}
        for k in key_values.keys():
            parts = k.split(":", 1)
            cat = parts[0]
            key_name = parts[1] if len(parts) > 1 else k
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append((k, key_name))

        for cat, items in sorted(by_category.items()):
            print(f"\n📂 Category: [{cat}]")
            for full_key, name in sorted(items):
                payload, is_expired = key_values[full_key]
                val = None
                if isinstance(payload, dict):
                    val = payload.get("value") or payload.get("summary") or payload
                else:
                    val = payload
                status_str = " (expired TTL)" if is_expired else ""
                print(f"  • {name} = {val}{status_str}")

    # 3. Inspect FAISS Vector DB Facts
    print("\n--- FAISS Vector Database Memories (Semantic Facts) ---")
    try:
        vector_facts = _load_vector_data()
        if not vector_facts:
            print("No semantic facts found in the vector store.")
        else:
            for idx, fact in enumerate(vector_facts, 1):
                print(f"  {idx}. \"{fact}\"")
    except Exception as e:
        print(f"⚠️ Error reading vector database: {e}")

    print("=" * 60)

if __name__ == "__main__":
    dump_memory()
