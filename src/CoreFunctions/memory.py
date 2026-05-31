import json
import os
import threading
from datetime import datetime

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
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

def _save(path, data):
    with _file_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

# -------------------------
# STORE MEMORY
# -------------------------
def store_memory(category, key, value):
    """
    category: current | user | past
    """
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
    data[key] = {
        "value": value,
        "timestamp": datetime.now().isoformat()
    }
    _save(FILES[category], data)
    print("📁 Writing memory to:", FILES[category])
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
        for cat in ("user", "current", "past"):
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

