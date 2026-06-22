import os
import sys
import json
from dotenv import load_dotenv

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Load env variables
load_dotenv(override=True)

from src.CoreFunctions.unified_memory import UnifiedMemory
from src.CoreFunctions.vector_memory import store_vector

BACKUP_DIR = os.path.join(os.path.dirname(__file__), "Memory", "backups")

def restore_backup(backup_file_path=None):
    print("=" * 60)
    print("🔄 Restoring Unified Memory Backup...")
    print("=" * 60)

    if not backup_file_path:
        backup_file_path = os.path.join(BACKUP_DIR, "latest_backup.json")

    if not os.path.exists(backup_file_path):
        print(f"⚠️ Error: Backup file not found at: {backup_file_path}")
        print("Please create a backup first or specify a valid file path.")
        print("=" * 60)
        return

    try:
        with open(backup_file_path, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
    except Exception as e:
        print(f"⚠️ Error reading backup file: {e}")
        print("=" * 60)
        return

    # 1. Restore Structured Memory
    um = UnifiedMemory()
    structured = backup_data.get("structured", {})
    
    if structured:
        if not um.enabled:
            print("Structured memory engine is disabled. Skipping structured restore.")
        else:
            try:
                print(f"Restoring {len(structured)} keys to structured memory...")
                for key, payload in structured.items():
                    # Extract values
                    val = payload.get("value")
                    if val is None:
                        # Fallback to key-value or extract value
                        val = payload.get("summary", payload)
                    
                    # Store
                    um.store_memory(
                        key, 
                        val, 
                        sharable=payload.get("sharable") == "yes",
                        persistent=payload.get("persistent") == "yes"
                    )
                print("✅ Structured memory restored successfully.")
            except Exception as e:
                print(f"⚠️ Error restoring structured memory: {e}")
    else:
        print("No structured keys found in backup.")

    # 2. Restore Vector Database
    vector = backup_data.get("vector", [])
    if vector:
        try:
            print(f"\nRestoring {len(vector)} semantic facts to vector database...")
            for fact in vector:
                print(f" • Writing: \"{fact}\"")
                store_vector(fact)
            print("✅ Vector database restored successfully.")
        except Exception as e:
            print(f"⚠️ Error restoring vector database: {e}")
    else:
        print("No semantic vector facts found in backup.")

    print("\n=" * 60)
    print("✨ Unified Memory restore completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    # Allow specifying a custom backup path via arguments
    custom_path = sys.argv[1] if len(sys.argv) > 1 else None
    restore_backup(custom_path)
