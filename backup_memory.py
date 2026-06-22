import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Load env variables
load_dotenv(override=True)

from src.CoreFunctions.unified_memory import UnifiedMemory
from src.CoreFunctions.vector_memory import _load_data as _load_vector_data

BACKUP_DIR = os.path.join(os.path.dirname(__file__), "Memory", "backups")

def create_backup():
    print("=" * 60)
    print("💾 Creating Unified Memory Backup...")
    print("=" * 60)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. Backup Structured Memory
    um = UnifiedMemory()
    structured_backup = {}
    
    if um.enabled:
        try:
            keys = um.list_keys("*")
            for k in keys:
                payload = um.retrieve_memory(k)
                if payload:
                    structured_backup[k] = payload
            print(f"📁 Read {len(structured_backup)} keys from structured memory.")
        except Exception as e:
            print(f"⚠️ Error reading structured memory: {e}")
    else:
        print("Unified Memory structured engine is disabled.")

    # 2. Backup Vector Store
    vector_backup = []
    try:
        vector_backup = _load_vector_data()
        print(f"📁 Read {len(vector_backup)} facts from FAISS vector database.")
    except Exception as e:
        print(f"⚠️ Error reading vector database: {e}")

    # Write backups
    backup_data = {
        "timestamp": datetime.now().isoformat(),
        "structured": structured_backup,
        "vector": vector_backup
    }
    
    backup_file = os.path.join(BACKUP_DIR, f"memory_backup_{timestamp}.json")
    latest_file = os.path.join(BACKUP_DIR, "latest_backup.json")
    
    try:
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=4)
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=4)
            
        print(f"\n✅ Backup saved successfully to:")
        print(f"   - {os.path.relpath(backup_file)}")
        print(f"   - {os.path.relpath(latest_file)}")
    except Exception as e:
        print(f"⚠️ Error writing backup files: {e}")

    print("=" * 60)

if __name__ == "__main__":
    create_backup()
