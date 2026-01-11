from googleapiclient.discovery import build
from CoreFunctions.auth_utils import get_valid_credentials
def get_tasks():
    """
    Fetches the top 10 tasks from the user's default task list.
    """
    creds = get_valid_credentials()
    if not creds:
        return []

    try:
        service = build('tasks', 'v1', credentials=creds)

        # 1. Get the default task list ID
        results = service.tasklists().list(maxResults=1).execute()
        items = results.get('items', [])

        if not items:
            return []

        tasklist_id = items[0]['id']

        # 2. Get tasks from that list
        tasks_result = service.tasks().list(
            tasklist=tasklist_id,
            maxResults=10,
            showCompleted=False # Only show pending tasks
        ).execute()

        tasks = tasks_result.get('items', [])
        
        clean_tasks = []
        for t in tasks:
            clean_tasks.append({
                "title": t['title'],
                "status": t['status'],
                "due": t.get('due', None) # Optional due date
            })

        return clean_tasks

    except Exception as e:
        print(f"⚠️ Tasks Error: {e}")
        return []
    
# Add this to the bottom of src/Apps/Google/tasks.py

def add_new_task(title):
    """
    Adds a new task to the default task list.
    """
    creds = get_valid_credentials()
    if not creds:
        return False

    try:
        service = build('tasks', 'v1', credentials=creds)

        # 1. Get default list ID
        results = service.tasklists().list(maxResults=1).execute()
        items = results.get('items', [])
        if not items:
            return False
        
        tasklist_id = items[0]['id']

        # 2. Insert the new task
        service.tasks().insert(
            tasklist=tasklist_id,
            body={'title': title}
        ).execute()
        
        return True

    except Exception as e:
        print(f"⚠️ Add Task Error: {e}")
        return False