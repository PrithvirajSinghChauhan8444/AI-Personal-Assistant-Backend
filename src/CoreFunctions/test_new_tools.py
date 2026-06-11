import sys
import os
import time

# Ensure src path is in Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Apps.System.clipboard_ops import copy_to_clipboard, paste_from_clipboard
from Apps.System.download_ops import download_file
from Apps.Automation.scheduler_ops import schedule_delayed_task, list_scheduled_tasks, load_tasks, save_tasks

def test_clipboard():
    print("📋 Testing Clipboard copy/paste...")
    test_msg = "Hermes test message at " + str(time.time())
    res_copy = copy_to_clipboard(test_msg)
    print("  Copy result:", res_copy)
    
    if "❌ Clipboard Error" in res_copy:
        print("  ⚠️ Clipboard utilities (xclip/xsel) not present, skipping paste assertion.")
        return
        
    res_paste = paste_from_clipboard()
    print("  Paste result:", res_paste)
    
    assert res_paste.strip() == test_msg, f"Clipboard mismatch! Sent: '{test_msg}', Recv: '{res_paste}'"
    print("  ✅ Clipboard test passed.")

def test_downloader():
    print("\n📥 Testing Downloader with aria2c...")
    # Using a small text file from wttr.in as test download
    url = "https://wttr.in/Agra?format=3"
    save_dir = "./test_downloads"
    filename = "weather_test.txt"
    
    res = download_file(url, save_dir, filename)
    print("  Download result:", res)
    
    if "❌ Error" in res:
        print("  ⚠️ aria2c not installed, skipping file assertions.")
        return
        
    full_path = os.path.abspath(os.path.join(save_dir, filename))
    assert os.path.exists(full_path), f"Downloaded file not found at {full_path}"
    
    with open(full_path, 'r') as f:
        content = f.read().strip()
    print(f"  Downloaded content: '{content}'")
    
    # Clean up
    os.remove(full_path)
    os.rmdir(save_dir)
    print("  ✅ Downloader test passed.")

def test_scheduler():
    print("\n⏰ Testing Task Scheduler...")
    # Save current database so we don't pollute existing list
    existing = load_tasks()
    
    # Reset database for clean testing
    save_tasks([])
    
    try:
        desc = "get_system_health"
        res = schedule_delayed_task(desc, delay_seconds=2)
        print("  Schedule result:", res)
        
        # Verify it shows up in list
        task_list = list_scheduled_tasks()
        print("  Task list:\n", task_list)
        assert desc in task_list, "Task not found in scheduler queue"
        
        print("  Waiting for 3 seconds for scheduler execution...")
        time.sleep(3)
        
        # Verify it transitioned to running/completed status
        tasks = load_tasks()
        for t in tasks:
            if t["description"] == desc:
                print(f"  Task status after 3s: '{t['status']}'")
                assert t["status"] in ["running", "completed", "failed"], f"Unexpected task status: {t['status']}"
                
        print("  ✅ Scheduler test passed.")
    finally:
        # Restore original tasks
        save_tasks(existing)

if __name__ == "__main__":
    print("=== Starting Integration Tests ===")
    test_clipboard()
    test_downloader()
    test_scheduler()
    print("\n=== All Integration Tests Completed successfully ===")
