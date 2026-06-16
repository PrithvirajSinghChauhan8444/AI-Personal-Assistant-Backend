import json
import os
import threading
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

# Thread lock to prevent race conditions during concurrent file accesses
_file_lock = threading.Lock()

def _load(path):
    with _file_lock:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return {}
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

def _save(path, data):
    with _file_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

# -------------------------
# STORE MEMORY
# -------------------------
import re

def store_memory(category, key, value):
    """
    category: current | user | past
    """
    # Validate the memory key format to prevent JSON property injection or path traversals
    if not isinstance(key, str) or not re.match(r"^[a-zA-Z0-9_\-]+$", key):
        raise ValueError("Invalid memory key: only alphanumeric characters, underscores, and dashes are allowed.")

    # Normalize category mapping to prevent LLM parameter hallucinations from crashing the tool
    category_str = str(category).lower()
    if category_str not in FILES:
        if "user" in category_str or "profile" in category_str:
            category = "user"
        else:
            category = "past"

    # Cross-check ALL structured memory JSON files to avoid duplicates and redundant entries
    normalized_key = key.strip().lower()
    normalized_val = str(value).strip().lower()

    for cat_name, file_path in FILES.items():
        existing_data = _load(file_path)
        for existing_key, existing_val_obj in existing_data.items():
            if existing_key.strip().lower() == normalized_key:
                val = existing_val_obj.get("value") if isinstance(existing_val_obj, dict) else existing_val_obj
                if str(val).strip().lower() == normalized_val:
                    print(f"ℹ️ [Structured Memory] Fact already exists in [{cat_name}] under '{existing_key}': \"{val}\". Skipping store.")
                    return f"Stored {key} in {category} memory (already exists)."
            
    data = _load(FILES[category])
    
    # Strip HTML tags/scripts from value as a sanitization guard
    sanitized_value = value
    if isinstance(value, str):
        sanitized_value = re.sub(r"<[^>]*>", "", value).strip()
        
    data[key] = {
        "value": sanitized_value,
        "timestamp": datetime.now().isoformat()
    }
    _save(FILES[category], data)
    print("📁 Writing memory to:", FILES[category])
    
    if category == "current":
        try:
            um = UnifiedMemory()
            if um.enabled:
                um.store_memory(key, sanitized_value, sharable=True, persistent=True)
                print(f"⚡ [UnifiedMemory] Stored '{key}' in workspace cache.")
        except Exception as um_err:
            print(f"⚠️ [UnifiedMemory] Failed to store in cache: {um_err}")

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

    # -----------------------------
    # SMART RECALL MODE
    # -----------------------------
    if category is None and key:
        # Check user
        user_data = _load(FILES["user"])
        if key in user_data:
            value = user_data[key].get("value")
            print(f"🔁 recalled [user] → {key} = {value}")
            return value

        # Check current / cache via UnifiedMemory first
        try:
            um = UnifiedMemory()
            if um.enabled:
                cache_val = um.retrieve_memory(key)
                if cache_val is not None:
                    value = cache_val.get("summary")
                    print(f"🔁 recalled [current] (UnifiedMemory) → {key} = {value}")
                    return value
        except Exception as um_err:
            print(f"⚠️ [UnifiedMemory] fetch error: {um_err}")

        # Fallback to local files for current and past
        for cat in ("current", "past"):
            data = _load(FILES[cat])
            if key in data:
                value = data[key].get("value")
                print(f"🔁 recalled [{cat}] → {key} = {value}")
                return value
        print(f"⚠️ recall miss → {key}")
        return None

    # -----------------------------
    # DIRECT CATEGORY MODE
    # -----------------------------
    if category and key:
        category_str = str(category).lower()
        if category_str not in FILES:
            if "user" in category_str or "profile" in category_str:
                category = "user"
            else:
                category = "past"

        if category == "current":
            try:
                um = UnifiedMemory()
                if um.enabled:
                    cache_val = um.retrieve_memory(key)
                    if cache_val is not None:
                        value = cache_val.get("summary")
                        print(f"🔁 recalled [{category}] (UnifiedMemory) → {key} = {value}")
                        return value
            except Exception as um_err:
                print(f"⚠️ [UnifiedMemory] fetch error: {um_err}")
                
        data = _load(FILES[category])
        value = data.get(key, {}).get("value")
        print(f"🔁 recalled [{category}] → {key} = {value}")
        return value

    # -----------------------------
    # FULL CATEGORY DUMP
    # -----------------------------
    if category:
        category_str = str(category).lower()
        if category_str not in FILES:
            if "user" in category_str or "profile" in category_str:
                category = "user"
            else:
                category = "past"
        return _load(FILES[category])

    return None

