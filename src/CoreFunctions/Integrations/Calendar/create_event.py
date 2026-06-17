from datetime import datetime, timedelta
from .calendar_service import get_service

def create_new_event(summary, start_time_iso, duration_hours=1, description=None, account: str = "personal"):
    """
    Creates a new event for a specific account.
    start_time_iso example: "2025-12-25T14:00:00"
    """
    service = get_service(account)
    if not service:
        return None

    # Calculate End Time and Normalize Start Time
    try:
        start_dt = datetime.fromisoformat(start_time_iso)
        # Ensure start_time has seconds (Google API requires it)
        start_time_iso = start_dt.isoformat(timespec='seconds')
        
        end_dt = start_dt + timedelta(hours=duration_hours)
        end_time_iso = end_dt.isoformat(timespec='seconds')
    except ValueError:
        print("❌ Error: Invalid date format.")
        return None

    event_body = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time_iso,
            'timeZone': 'Asia/Kolkata', 
        },
        'end': {
            'dateTime': end_time_iso,
            'timeZone': 'Asia/Kolkata',
        },
    }

    try:
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        print(f"✅ Created: {summary} on account '{account}' ({event.get('htmlLink')})")
        return event
    except Exception as e:
        print(f"❌ Create Error on account '{account}': {e}")
        return None