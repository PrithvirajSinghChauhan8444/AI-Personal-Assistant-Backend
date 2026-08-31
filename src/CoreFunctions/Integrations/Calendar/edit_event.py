from datetime import datetime, timedelta
from .calendar_service import get_service
from .calendar_colors import resolve_calendar_color_id

def edit_existing_event(
    event_id: str,
    summary: str = None,
    start_time_iso: str = None,
    duration_hours: float = None,
    description: str = None,
    color: str = None,
    account: str = "personal"
):
    """
    Edits an existing Google Calendar event by its event_id.
    """
    service = get_service(account)
    if not service:
        return None

    try:
        current_event = service.events().get(calendarId='primary', eventId=event_id).execute()
    except Exception as e:
        print(f"❌ Error fetching event '{event_id}' on account '{account}': {e}")
        return None

    patch_body = {}

    if summary is not None:
        patch_body['summary'] = summary

    if color is not None:
        patch_body['colorId'] = resolve_calendar_color_id(color)

    if description is not None:
        ai_note = "This event was added by the AI assistant."
        if str(description).strip():
            desc_str = str(description).strip()
            if "added by the ai assistant" in desc_str.lower() or "added by ai assistant" in desc_str.lower():
                final_description = desc_str
            else:
                final_description = f"{desc_str}\n\n{ai_note}"
        else:
            final_description = ai_note
        patch_body['description'] = final_description

    if start_time_iso is not None:
        try:
            start_dt = datetime.fromisoformat(start_time_iso)
            start_time_iso = start_dt.isoformat(timespec='seconds')
            
            if duration_hours is not None:
                end_dt = start_dt + timedelta(hours=duration_hours)
            else:
                curr_start = current_event.get('start', {}).get('dateTime')
                curr_end = current_event.get('end', {}).get('dateTime')
                if curr_start and curr_end:
                    try:
                        curr_start_dt = datetime.fromisoformat(curr_start)
                        curr_end_dt = datetime.fromisoformat(curr_end)
                        orig_duration = curr_end_dt - curr_start_dt
                        end_dt = start_dt + orig_duration
                    except Exception:
                        end_dt = start_dt + timedelta(hours=1)
                else:
                    end_dt = start_dt + timedelta(hours=1)

            end_time_iso = end_dt.isoformat(timespec='seconds')
            patch_body['start'] = {
                'dateTime': start_time_iso,
                'timeZone': 'Asia/Kolkata',
            }
            patch_body['end'] = {
                'dateTime': end_time_iso,
                'timeZone': 'Asia/Kolkata',
            }
        except ValueError:
            print("❌ Error: Invalid date format for start_time_iso.")
            return None
    elif duration_hours is not None:
        curr_start = current_event.get('start', {}).get('dateTime')
        if curr_start:
            try:
                curr_start_dt = datetime.fromisoformat(curr_start)
                end_dt = curr_start_dt + timedelta(hours=duration_hours)
                patch_body['end'] = {
                    'dateTime': end_dt.isoformat(timespec='seconds'),
                    'timeZone': 'Asia/Kolkata',
                }
            except Exception as e:
                print(f"❌ Error updating duration: {e}")

    if not patch_body:
        print("⚠️ Warning: No fields provided to edit.")
        return current_event

    try:
        updated_event = service.events().patch(calendarId='primary', eventId=event_id, body=patch_body).execute()
        print(f"✅ Updated event '{event_id}' on account '{account}' ({updated_event.get('htmlLink')})")
        return updated_event
    except Exception as e:
        print(f"❌ Update Error on account '{account}': {e}")
        return None
