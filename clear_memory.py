import os
import sys
import shutil
from dotenv import load_dotenv

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Load env variables
load_dotenv(override=True)

from src.CoreFunctions.unified_memory import UnifiedMemory

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
            keys = um.list_keys("*")
            if not keys:
                print("No structured keys found to clear.")
            else:
                print(f"Deleting {len(keys)} structured keys...")
                for k in keys:
                    um.delete_memory(k)
                print("✅ Structured memory cleared.")
        except Exception as e:
            print(f"⚠️ Error clearing structured memory: {e}")

    # 2. Reset General FAISS Vector Database
    print("\n--- Resetting General Semantic Vector Store ---")
    vector_dir = os.path.join(os.path.dirname(__file__), "Memory", "vector_store")
    index_path = os.path.join(vector_dir, "index.faiss")
    data_path = os.path.join(vector_dir, "data.json")
    
    deleted_any = False
    for path in [index_path, data_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"🗑️ Deleted: {os.path.basename(path)}")
                deleted_any = True
            except Exception as e:
                print(f"⚠️ Error deleting {path}: {e}")
                
    if deleted_any:
        print("✅ General semantic vector store cleared.")
    else:
        print("General semantic vector store was already empty.")

    print("\n=" * 60)
    print("✨ Unified Memory has been successfully reset!")
    print("=" * 60)

if __name__ == "__main__":
    clear_unified_memory()
