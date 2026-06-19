import os
import sys
import json
from dotenv import load_dotenv

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Load .env
load_dotenv(override=True)

from src.CoreFunctions.unified_memory import UnifiedMemory
from src.CoreFunctions.vector_memory import _load_data as _load_vector_data

def dump_memory():
    print("=" * 60)
    print("📋 Unified Memory System Current Contents")
    print("=" * 60)

    # 1. Inspect Structured Memory (SQLite/Redis/Postgres)
    um = UnifiedMemory()
    print(f"\n⚙️  Active Cache Provider: {um.engine.__class__.__name__}")
    if hasattr(um.engine, 'db_path'):
        print(f"📁 Local DB Path: {um.engine.db_path}")

    print("\n--- Structured Memory Keys (SQLite/Redis/Postgres) ---")
    if not um.enabled:
        print("Unified Memory is disabled.")
    else:
        try:
            keys = um.list_keys("*")
            if not keys:
                print("No structured keys found in the database.")
            else:
                # Group keys by category for cleaner display
                by_category = {}
                for k in keys:
                    parts = k.split(":", 1)
                    cat = parts[0]
                    key_name = parts[1] if len(parts) > 1 else k
                    if cat not in by_category:
                        by_category[cat] = []
                    by_category[cat].append((k, key_name))

                for cat, items in sorted(by_category.items()):
                    print(f"\n📂 Category: [{cat}]")
                    for full_key, name in sorted(items):
                        payload = um.retrieve_memory(full_key)
                        val = payload.get("value") if payload else None
                        print(f"  • {name} = {val}")
        except Exception as e:
            print(f"⚠️ Error reading structured memory: {e}")

    # 2. Inspect FAISS Vector DB Facts
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
