import json
import os
from datetime import datetime

# Absolute path relative to project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEMORY_DIR = os.path.join(BASE_DIR, "Memory")

FILES = {
    "current": os.path.join(MEMORY_DIR, "current_chat.json"),
    "user": os.path.join(MEMORY_DIR, "user_info.json"),
    "past": os.path.join(MEMORY_DIR, "past_memory.json"),
}

def _load(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# -------------------------
# STORE MEMORY
# -------------------------
def store_memory(category, key, value):
    """
    category: current | user | past
    """
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
        data = _load(FILES[category])
        value = data.get(key, {}).get("value")
        print(f"🔁 recalled [{category}] → {key} = {value}")
        return value

    # -----------------------------
    # FULL CATEGORY DUMP
    # -----------------------------
    if category:
        return _load(FILES[category])

    return None
