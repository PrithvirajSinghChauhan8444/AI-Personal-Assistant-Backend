import os
import sys
import shutil
import sqlite3
from dotenv import load_dotenv

# Add src and workspace to python path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(BASE_DIR, 'src'))

# Load env variables
load_dotenv(override=True)

from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory

def clear_unified_memory():
    print("=" * 60)
    print("🧹 Clearing Unified Memory System...")
    print("=" * 60)

    # 1. Clear Structured Memory
    um = UnifiedMemory()
    print(f"\n⚙️  Active Cache Provider: {um.engine.__class__.__name__}")
    
    if not um.enabled:
        print("Unified Memory is disabled.")
    else:
        try:
            # Delete keys from main and sharded engine
            keys = um.list_keys("*")
            if not keys:
                print("No structured keys found to clear.")
            else:
                print(f"Deleting {len(keys)} structured keys...")
                for k in keys:
                    um.delete_memory(k)
                print("✅ Structured memory keys cleared.")
                
            # Truncate relations and new refactored tables if SQLite database is used
            from src.CoreFunctions.Infrastructure.unified_memory import SQLiteMemoryEngine
            if isinstance(um.engine, SQLiteMemoryEngine):
                db_path = um.engine.db_path
                conn = sqlite3.connect(db_path)
                try:
                    tables = ["relations", "people", "profile", "profile_review_queue", "events", "vector_facts"]
                    for t in tables:
                        try:
                            conn.execute(f"DELETE FROM {t}")
                            print(f"✅ SQLite {t} table truncated.")
                        except sqlite3.OperationalError:
                            pass
                    conn.commit()
                except Exception as e:
                    print(f"⚠️ Error truncating SQLite tables: {e}")
                finally:
                    conn.close()
        except Exception as e:
            print(f"⚠️ Error clearing structured memory: {e}")

    # 2. Clear SQLite Shards directory
    shards_dir = os.path.join(BASE_DIR, "Memory", "shards")
    if os.path.exists(shards_dir):
        print(f"\n📁 Clearing sharded SQLite databases in '{shards_dir}'...")
        try:
            shutil.rmtree(shards_dir)
            os.makedirs(shards_dir, exist_ok=True)
            print("✅ SQLite shards cleared.")
        except Exception as e:
            print(f"⚠️ Error clearing SQLite shards: {e}")

    # 3. Clear Chat Archive Database
    chat_archive = os.path.join(BASE_DIR, "Memory", "chat_archive.db")
    if os.path.exists(chat_archive):
        print(f"\n💬 Clearing Conversational FTS5 Chat Archive...")
        try:
            os.remove(chat_archive)
            print("✅ Chat archive database deleted.")
        except Exception as e:
            print(f"⚠️ Error deleting chat archive: {e}")

    # 4. Reset General FAISS Vector Database and Metadata
    print("\n--- Resetting General Semantic Vector Store ---")
    vector_dir = os.path.join(BASE_DIR, "Memory", "vector_store")
    index_path = os.path.join(vector_dir, "index.faiss")
    data_path = os.path.join(vector_dir, "data.json")
    metadata_path = os.path.join(vector_dir, "metadata.json")
    cold_archive_path = os.path.join(vector_dir, "cold_archive.json")
    
    deleted_any = False
    for path in [index_path, data_path, metadata_path, cold_archive_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"🗑️ Deleted: {os.path.basename(path)}")
                deleted_any = True
            except Exception as e:
                print(f"⚠️ Error deleting {path}: {e}")
                
    if deleted_any:
        print("✅ General semantic vector store and metadata cleared.")
    else:
        print("General semantic vector store was already empty.")

    print("\n=" * 60)
    print("✨ Unified Memory has been successfully reset!")
    print("=" * 60)

if __name__ == "__main__":
    clear_unified_memory()
