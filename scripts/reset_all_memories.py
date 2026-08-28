import os
import shutil
import redis
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(BASE_DIR, "Memory")

def reset():
    print("🚨 Starting Hard Reset of All Memories & Databases...")

    # 1. Flush Redis
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            r = redis.from_url(redis_url)
            r.flushall()
            print("✅ Flushed all Redis keys.")
        except Exception as e:
            print(f"⚠️ Redis flush failed: {e}")

    # 2. Delete specific databases and files in Memory/
    paths_to_delete = [
        os.path.join(MEMORY_DIR, "workspace_cache.db"),
        os.path.join(MEMORY_DIR, "gmail_worker.db"),
        os.path.join(MEMORY_DIR, "file_manifest.db"),
        os.path.join(MEMORY_DIR, "chat_archive.db"),
        os.path.join(MEMORY_DIR, "session_context.json"),
        os.path.join(MEMORY_DIR, "reflection.log"),
        os.path.join(MEMORY_DIR, "past_memory.json.bak"),
        os.path.join(MEMORY_DIR, "user_info.json"),
        os.path.join(MEMORY_DIR, "user_info.json.bak"),
        os.path.join(MEMORY_DIR, "current_chat.json.bak"),
    ]

    for p in paths_to_delete:
        if os.path.exists(p):
            try:
                os.remove(p)
                print(f"🗑️ Deleted file: {os.path.basename(p)}")
            except Exception as e:
                print(f"⚠️ Failed to delete {p}: {e}")

    # 3. Clean directories
    dirs_to_clean = [
        os.path.join(MEMORY_DIR, "shards"),
        os.path.join(MEMORY_DIR, "vector_store"),
        os.path.join(MEMORY_DIR, "backups"),
    ]

    for d in dirs_to_clean:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                os.makedirs(d, exist_ok=True)
                print(f"🗑️ Cleared directory: {os.path.basename(d)}")
            except Exception as e:
                print(f"⚠️ Failed to clear directory {d}: {e}")

    # 4. Reset JSON configuration files
    scheduled_tasks_path = os.path.join(MEMORY_DIR, "scheduled_tasks.json")
    try:
        with open(scheduled_tasks_path, "w") as f:
            f.write("{}")
        print("📝 Reset scheduled_tasks.json to default empty object.")
    except Exception as e:
        print(f"⚠️ Failed to reset scheduled_tasks.json: {e}")

    print("\n🎉 Hard reset complete! All memories have been cleared and started fresh.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    reset()
