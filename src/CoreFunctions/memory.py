import json
import os
import re
from datetime import datetime
from CoreFunctions.unified_memory import UnifiedMemory

# Absolute path relative to project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEMORY_DIR = os.path.join(BASE_DIR, "Memory")

FILES = {
    "current": os.path.join(MEMORY_DIR, "current_chat.json"),
    "user": os.path.join(MEMORY_DIR, "user_info.json"),
    "past": os.path.join(MEMORY_DIR, "past_memory.json"),
}

# -------------------------
# MIGRATION UTILITY
# -------------------------
def migrate_json_to_sqlite():
    """Migrates legacy flat JSON files to the unified database cache on startup."""
    um = UnifiedMemory()
    if not um.enabled:
        return
        
    for category, path in FILES.items():
        if os.path.exists(path) and os.path.getsize(path) > 0:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                migrated_count = 0
                for key, val_obj in data.items():
                    # Extract the value and timestamp
                    if isinstance(val_obj, dict):
                        val = val_obj.get("value")
                        ts = val_obj.get("timestamp", datetime.now().isoformat())
                    else:
                        val = val_obj
                        ts = datetime.now().isoformat()
                    
                    db_key = f"{category}:{key}"
                    um.store_memory(db_key, {
                        "value": val,
                        "timestamp": ts
                    }, persistent=True)
                    migrated_count += 1
                
                if migrated_count > 0:
                    print(f"📦 [Database Memory Migration] Migrated {migrated_count} keys from '{category}' file to database cache.")
                
                # Backup the file to avoid re-migrating
                backup_path = path + ".bak"
                if os.path.exists(backup_path):
                    try:
                        os.remove(backup_path)
                    except Exception:
                        pass
                os.rename(path, backup_path)
                print(f"📦 [Database Memory Migration] Backed up legacy file '{path}' to '{backup_path}'.")
            except Exception as e:
                print(f"⚠️ [Database Memory Migration] Error migrating '{path}': {e}")

# Run automatic migration on load
migrate_json_to_sqlite()

# -------------------------
# STORE MEMORY
# -------------------------
def store_memory(category, key, value):
    """
    Stores structured user/past/current memory in the unified database engine.
    """
    # Validate the memory key format to prevent JSON property injection or path traversals
    if not isinstance(key, str) or not re.match(r"^[a-zA-Z0-9_\-]+$", key):
        raise ValueError("Invalid memory key: only alphanumeric characters, underscores, and dashes are allowed.")

    # Normalize category mapping
    category_str = str(category).lower()
    if category_str not in ["current", "user", "past"]:
        if "user" in category_str or "profile" in category_str:
            category = "user"
        else:
            category = "past"
    else:
        category = category_str

    # Strip HTML tags/scripts from value as a sanitization guard
    sanitized_value = value
    if isinstance(value, str):
        sanitized_value = re.sub(r"<[^>]*>", "", value).strip()

    um = UnifiedMemory()
    db_key = f"{category}:{key}"

    # Cross-check ALL categories to avoid duplicates
    normalized_key = key.strip().lower()
    normalized_val = str(sanitized_value).strip().lower()

    for cat in ["current", "user", "past"]:
        cat_keys = um.list_keys(f"{cat}:*")
        for ck in cat_keys:
            orig_k = ck.split(":", 1)[1]
            if orig_k.strip().lower() == normalized_key:
                payload = um.retrieve_memory(ck)
                if payload:
                    val = payload.get("value")
                    if str(val).strip().lower() == normalized_val:
                        print(f"ℹ️ [Structured Memory] Fact already exists in [{cat}] under '{orig_k}': \"{val}\". Skipping store.")
                        return f"Stored {key} in {category} memory (already exists)."

    # Save to SQLite/Redis via UnifiedMemory
    um.store_memory(db_key, {
        "value": sanitized_value,
        "timestamp": datetime.now().isoformat()
    }, persistent=True)
    print(f"📁 Writing memory to database: {db_key}")

    return f"Stored {key} in {category} memory."

# -------------------------
# FETCH MEMORY
# -------------------------
def fetch_memory(category=None, key=None):
    """
    Fetch memory value.

    If category is provided:
        fetch_memory("user", "name")

    If category is None:
        smart lookup in order:
        user → current → past
    """
    um = UnifiedMemory()
    if not um.enabled:
        return None

    # -----------------------------
    # SMART RECALL MODE
    # -----------------------------
    if category is None and key:
        # Check user
        user_val = um.retrieve_memory(f"user:{key}")
        if user_val is not None:
            value = user_val.get("value")
            print(f"🔁 recalled [user] → {key} = {value}")
            return value

        # Check current
        current_val = um.retrieve_memory(f"current:{key}")
        if current_val is not None:
            value = current_val.get("value")
            print(f"🔁 recalled [current] → {key} = {value}")
            return value

        # Check past
        past_val = um.retrieve_memory(f"past:{key}")
        if past_val is not None:
            value = past_val.get("value")
            print(f"🔁 recalled [past] → {key} = {value}")
            return value

        print(f"⚠️ recall miss → {key}")
        return None

    # -----------------------------
    # DIRECT CATEGORY MODE
    # -----------------------------
    if category and key:
        category_str = str(category).lower()
        if category_str not in ["current", "user", "past"]:
            if "user" in category_str or "profile" in category_str:
                category = "user"
            else:
                category = "past"
        else:
            category = category_str

        db_key = f"{category}:{key}"
        val_obj = um.retrieve_memory(db_key)
        if val_obj is not None:
            value = val_obj.get("value")
            print(f"🔁 recalled [{category}] → {key} = {value}")
            return value
        return None

    # -----------------------------
    # FULL CATEGORY DUMP
    # -----------------------------
    if category:
        category_str = str(category).lower()
        if category_str not in ["current", "user", "past"]:
            if "user" in category_str or "profile" in category_str:
                category = "user"
            else:
                category = "past"
        else:
            category = category_str

        category_keys = um.list_keys(f"{category}:*")
        dump = {}
        for ck in category_keys:
            orig_k = ck.split(":", 1)[1]
            payload = um.retrieve_memory(ck)
            if payload:
                dump[orig_k] = {
                    "value": payload.get("value"),
                    "timestamp": payload.get("timestamp", datetime.now().isoformat())
                }
        return dump

    return None


def delete_memory(category, key):
    """
    Deletes a memory key from the database.
    """
    category_str = str(category).lower()
    if category_str not in ["current", "user", "past"]:
        if "user" in category_str or "profile" in category_str:
            category = "user"
        else:
            category = "past"
    else:
        category = category_str

    um = UnifiedMemory()
    db_key = f"{category}:{key}"
    um.delete_memory(db_key)
    print(f"🗑️ Deleted memory key from database: {db_key}")
    return f"Deleted memory '{key}' from '{category}' memory."
