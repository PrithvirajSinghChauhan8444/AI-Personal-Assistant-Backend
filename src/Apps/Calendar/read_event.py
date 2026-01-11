from datetime import datetime, timezone
from .calendar_service import get_service

def list_upcoming_events(max_results=10):
    """
    Fetches the next 10 upcoming events.
    """
    service = get_service()
    if not service:
        return []

    # --- FIX: Use timezone-aware UTC time ---
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    try:
        print(f"📅 Checking calendar for next {max_results} events...")
        events_result = service.events().list(
            calendarId='primary', 
            timeMin=now,
            maxResults=max_results, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        clean_events = []
        for event in events:
            # Handle full-day events (which use 'date') vs timed events (which use 'dateTime')
            start = event['start'].get('dateTime', event['start'].get('date'))
            clean_events.append({
                'summary': event.get('summary', '(No Title)'),
                'start': start,
                'link': event.get('htmlLink')
            })
            
        return clean_events

    except Exception as e:
        print(f"❌ Read Error: {e}")
        return []

# --- Test Block ---
if __name__ == "__main__":
    events = list_upcoming_events()
    
    if not events:
        print("📭 No upcoming events found on your primary calendar.")
    else:
        print(f"\n✅ Found {len(events)} events:")
        for e in events:
            print(f"- {e['summary']} at {e['start']}")