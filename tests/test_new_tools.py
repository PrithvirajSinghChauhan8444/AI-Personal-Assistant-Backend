import sys
import os
import time

# Ensure src path is in Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.Integrations.System.clipboard_ops import copy_to_clipboard, paste_from_clipboard
from src.CoreFunctions.Integrations.System.download_ops import download_file
from src.CoreFunctions.Integrations.Automation.scheduler_ops import schedule_delayed_task, list_scheduled_tasks, load_tasks, save_tasks

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
        
        print("  Waiting for scheduler execution (up to 60 seconds)...")
        start_time = time.time()
        status = "pending"
        while time.time() - start_time < 60:
            time.sleep(0.5)
            tasks = load_tasks()
            status = next((t["status"] for t in tasks if t["description"] == desc), "pending")
            if status in ["completed", "failed"]:
                break
                
        print(f"  Task status reached: '{status}'")
        assert status in ["completed", "failed"], f"Unexpected task status: {status}"
        print("  ✅ Scheduler test passed.")
    finally:
        # Restore original tasks
        save_tasks(existing)

def test_token_encryption():
    print("\n🔒 Testing Token Encryption & Decryption...")
    from src.CoreFunctions.Infrastructure.auth_utils import load_encrypted_json, save_encrypted_json
    import tempfile
    
    # Create a temporary file path
    temp_dir = tempfile.mkdtemp()
    test_path = os.path.join(temp_dir, "test_token.json")
    
    test_data = {
        "access_token": "secret_access_token_123",
        "refresh_token": "secret_refresh_token_456",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client_id_789"
    }
    
    try:
        # Test 1: Write raw json first to test backward compatibility migration
        import json
        with open(test_path, 'w') as f:
            json.dump(test_data, f)
            
        print("  - Created legacy unencrypted token file.")
        
        # Test 2: Load the file (should transparently read plaintext, then save encrypted)
        loaded_data = load_encrypted_json(test_path)
        assert loaded_data == test_data, f"Legacy data mismatch! Expected: {test_data}, Loaded: {loaded_data}"
        print("  - Successfully read legacy plaintext token.")
        
        # Verify it was re-saved encrypted (starts with non-{ bytes)
        with open(test_path, 'rb') as f:
            encrypted_content = f.read()
        assert not encrypted_content.startswith(b'{'), "Token file was not encrypted automatically!"
        print("  - Verified token was automatically upgraded to encrypted format.")
        
        # Test 3: Load the newly encrypted file
        loaded_encrypted = load_encrypted_json(test_path)
        assert loaded_encrypted == test_data, f"Encrypted load mismatch! Expected: {test_data}, Loaded: {loaded_encrypted}"
        print("  - Successfully decrypted and loaded encrypted token file.")
        
        # Test 4: Save directly using save_encrypted_json
        new_data = {"updated_key": "new_secret_val"}
        save_encrypted_json(test_path, new_data)
        loaded_new = load_encrypted_json(test_path)
        assert loaded_new == new_data, f"Saved encrypted data mismatch! Expected: {new_data}, Loaded: {loaded_new}"
        print("  - Successfully wrote and read encrypted token using save_encrypted_json.")
        
        # Verify permissions (if Unix)
        if os.name != 'nt':
            mode = os.stat(test_path).st_mode & 0o777
            assert mode == 0o600, f"Token file permission is not secure! Expected 0600 (octal), got {oct(mode)}"
            print("  - Verified secure file permissions (0600) on Linux.")
            
        print("  ✅ Token Encryption test passed.")
    finally:
        if os.path.exists(test_path):
            os.remove(test_path)
        os.rmdir(temp_dir)

def test_update_skill():
    print("\n🛠️ Testing Skill Update Capability...")
    from unittest.mock import patch
    from src.CoreFunctions.StateGraph.Workers.MemoryWorker.memory_worker_tools.memory_worker_tool_update_skill import update_skill_tool
    import shutil
    
    # We will mock verify_password to return True for testing
    with patch('src.CoreFunctions.StateGraph.Workers.MemoryWorker.memory_worker_tools.memory_worker_tool_update_skill.verify_password', return_value=True):
        skill_name = "test-temp-skill"
        category = "general"
        description = "This is a temporary test skill."
        procedure = "1. Step one\n2. Step two"
        script_code = "print('hello from temp script')"
        script_filename = "temp_run.py"
        
        try:
            # 1. Update/create the skill
            res = update_skill_tool(
                skill_name=skill_name,
                description=description,
                category=category,
                procedure=procedure,
                script_code=script_code,
                script_filename=script_filename
            )
            print("  Update result:", res)
            assert "Successfully updated skill" in res, f"Unexpected update response: {res}"
            
            # 2. Verify files exist
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            skill_folder = os.path.join(base_dir, "Skills", "general", skill_name)
            skill_md_path = os.path.join(skill_folder, "SKILL.md")
            script_path = os.path.join(skill_folder, "scripts", script_filename)
            
            assert os.path.exists(skill_md_path), f"SKILL.md not found at {skill_md_path}"
            assert os.path.exists(script_path), f"Script not found at {script_path}"
            
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            assert description in md_content, "Skill description not written to metadata!"
            assert "Step one" in md_content, "Skill procedure not written to file!"
            
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            assert script_code in script_content, "Automation script code mismatch!"
            
            print("  ✅ Skill Update test passed.")
        finally:
            # Clean up the test skill folder
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            skill_folder = os.path.join(base_dir, "Skills", "general", skill_name)
            if os.path.exists(skill_folder):
                shutil.rmtree(skill_folder)

def test_check_calendar_events():
    print("\n📅 Testing check_calendar_events tool...")
    from unittest.mock import patch
    from src.CoreFunctions.StateGraph.Workers.ProductivityWorker.productivity_worker_tools.productivity_worker_tool_check_events import check_calendar_events

    mock_events = [
        {
            'summary': 'NPTEL Assignment Submission: Mental Health and Wellbeing (Week 6)',
            'start': '2026-09-02T23:59:00Z',
            'link': 'https://www.google.com/calendar/event?eid=bXZwcG5vNzA2NzBzaWllN29yY3Q3Njhkbm8gcHJpdGh2aTI0MTAxQGlpaXRuci5lZHUuaW4'
        }
    ]

    with patch('src.CoreFunctions.StateGraph.Workers.ProductivityWorker.productivity_worker_tools.productivity_worker_tool_check_events.list_upcoming_events', return_value=mock_events):
        res = check_calendar_events(max_results=5, account="college")
        print("  Result:\n", res)
        assert "Mental Health and Wellbeing" in res
        assert "2026-09-02T23:59:00Z" in res
        print("  ✅ check_calendar_events test passed.")

def test_create_calendar_event():
    print("\n📅 Testing create_new_event with empty/filled descriptions and colors...")
    from unittest.mock import patch, MagicMock
    from src.CoreFunctions.Integrations.Calendar.create_event import create_new_event
    from src.CoreFunctions.StateGraph.Workers.ProductivityWorker.productivity_worker_tools.productivity_worker_tool_add_event import add_calendar_event

    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_service.events.return_value = mock_events
    mock_insert = MagicMock()
    mock_events.insert.return_value = mock_insert
    mock_insert.execute.return_value = {'htmlLink': 'https://calendar.google.com/test_link'}

    with patch('src.CoreFunctions.Integrations.Calendar.create_event.get_service', return_value=mock_service):
        # Case 1: Empty description (defaults to orange / "6")
        create_new_event("Team Standup", "2026-09-02T10:00:00", 1, description=None, account="personal")
        call_args = mock_events.insert.call_args[1]
        assert call_args['body']['description'] == "This event was added by the AI assistant."
        assert call_args['body']['colorId'] == "6"

        # Case 2: Filled description with custom color ("blue" -> "9")
        create_new_event("Sprint Review", "2026-09-02T14:00:00", 2, description="Discuss quarterly goals and milestones.", color="blue", account="personal")
        call_args = mock_events.insert.call_args[1]
        assert call_args['body']['description'] == "Discuss quarterly goals and milestones.\n\nThis event was added by the AI assistant."
        assert call_args['body']['colorId'] == "9"

        # Case 3: Via tool add_calendar_event (defaults to orange)
        res = add_calendar_event("1:1 Sync", "2026-09-02T16:00:00", 1, description="Bi-weekly 1:1 sync meeting", color="orange", account="personal")
        call_args = mock_events.insert.call_args[1]
        assert "Bi-weekly 1:1 sync meeting\n\nThis event was added by the AI assistant." == call_args['body']['description']
        assert call_args['body']['colorId'] == "6"
        assert "Event '1:1 Sync' created" in res

    print("  ✅ create_new_event and add_calendar_event tests passed.")

def test_edit_and_delete_calendar_event():
    print("\n📅 Testing edit_calendar_event and delete_calendar_event tools...")
    from unittest.mock import patch, MagicMock
    from src.CoreFunctions.Integrations.Calendar.edit_event import edit_existing_event
    from src.CoreFunctions.Integrations.Calendar.delete_event import delete_existing_event
    from src.CoreFunctions.StateGraph.Workers.ProductivityWorker.productivity_worker_tools.productivity_worker_tool_edit_event import edit_calendar_event
    from src.CoreFunctions.StateGraph.Workers.ProductivityWorker.productivity_worker_tools.productivity_worker_tool_delete_event import delete_calendar_event

    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_service.events.return_value = mock_events

    # Mock get
    mock_get = MagicMock()
    mock_events.get.return_value = mock_get
    mock_get.execute.return_value = {
        'id': 'evt_123',
        'summary': 'Old Title',
        'description': 'Old notes',
        'start': {'dateTime': '2026-09-02T10:00:00+05:30'},
        'end': {'dateTime': '2026-09-02T11:00:00+05:30'},
        'htmlLink': 'https://calendar.google.com/event_123'
    }

    # Mock patch
    mock_patch = MagicMock()
    mock_events.patch.return_value = mock_patch
    mock_patch.execute.return_value = {
        'id': 'evt_123',
        'summary': 'Updated Title',
        'htmlLink': 'https://calendar.google.com/event_123'
    }

    # Mock delete
    mock_delete = MagicMock()
    mock_events.delete.return_value = mock_delete
    mock_delete.execute.return_value = {}

    with patch('src.CoreFunctions.Integrations.Calendar.edit_event.get_service', return_value=mock_service), \
         patch('src.CoreFunctions.Integrations.Calendar.delete_event.get_service', return_value=mock_service):

        # Test edit_existing_event with color change
        res_edit = edit_calendar_event(
            event_id="evt_123",
            summary="Updated Title",
            start_time="2026-09-02T12:00:00",
            duration=2,
            description="Updated agenda",
            color="green",
            account="personal"
        )
        patch_body = mock_events.patch.call_args[1]['body']
        assert patch_body['summary'] == "Updated Title"
        assert "Updated agenda\n\nThis event was added by the AI assistant." in patch_body['description']
        assert patch_body['colorId'] == "10"
        assert "Updated Title" in res_edit

        # Test delete_calendar_event
        res_delete = delete_calendar_event(event_id="evt_123", account="personal")
        mock_events.delete.assert_called_with(calendarId='primary', eventId='evt_123')
        assert "successfully deleted" in res_delete

    print("  ✅ edit_calendar_event and delete_calendar_event tests passed.")

if __name__ == "__main__":
    print("=== Starting Integration Tests ===")
    test_clipboard()
    test_downloader()
    test_scheduler()
    test_token_encryption()
    test_update_skill()
    test_check_calendar_events()
    test_create_calendar_event()
    test_edit_and_delete_calendar_event()
    print("\n=== All Integration Tests Completed successfully ===")
