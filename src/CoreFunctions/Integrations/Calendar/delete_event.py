from .calendar_service import get_service

def delete_existing_event(event_id: str, account: str = "personal") -> bool:
    """
    Deletes an event from Google Calendar by its event_id.
    """
    service = get_service(account)
    if not service:
        return False

    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        print(f"✅ Deleted event '{event_id}' on account '{account}'.")
        return True
    except Exception as e:
        print(f"❌ Delete Error on account '{account}': {e}")
        return False
