import requests
import time
import re
from .config import BASE_URL, get_headers
from .session import start_session
from .contacts import resolve_to_number

def format_phone_number(phone):
    """
    Formats phone number to WAHA chat ID.
    - Removes non-digits.
    - Adds default country code '91' (India) if length is 10.
    """
    # If it already looks like an ID (contains @), return it as is
    if "@" in str(phone):
        return phone

    clean_number = re.sub(r'\D', '', str(phone))
    
    if len(clean_number) == 10:
        clean_number = '91' + clean_number
    
    return f"{clean_number}@c.us"

def send_message(phone, message, session_name="default"):
    """
    Sends a WhatsApp message.
    - phone: 
        - Can be a direct ID '9876543210' OR '12036...@g.us'
        - OR a Contact Name 'Praveen' (will trigger interactive check)
    - message: Text string
    """
    
    # --- Step 1: Resolve Contact ---
    target_id = None
    
    # Check if input is likely a Name or a Number
    is_likely_number = re.match(r'^\+?\d{10,15}$', str(phone)) or "@" in str(phone)
    
    if is_likely_number:
        target_id = format_phone_number(phone)
    else:
        # It's a name, let's resolve it
        print(f"🔍 Searching contact for: '{phone}'...")
        matches = resolve_to_number(phone, session_name)
        
        if not matches:
             return f"❌ Could not find any contact matching '{phone}'."
        
        target_id = None
        selected_match = None

        # Check for Cached Alias Match
        if len(matches) == 1 and matches[0].get('source') == 'cache':
            # It's a known alias!
            m = matches[0]
            print(f"✅ Found cached alias: '{m['referred']}' -> {m['name']} ({m['id']})")
            # Auto-confirm or minimal confirmation
            # For safety, let's do a quick confirm, but defaulting to yes
            confirm = input(f"Send to {m['name']}? [Y/n]: ").strip().lower()
            if confirm in ('', 'y', 'yes'):
                target_id = m['id']
            else:
                return "❌ Action cancelled by user."

        else:
            # Interactive Confirmation Loop for Online Search Results
            confirmed = False
            for attempt in range(3):
                print(f"\nFound {len(matches)} potential contacts for '{phone}':")
                for i, m in enumerate(matches[:5]): # Show top 5
                    print(f" {i+1}. {m['name']} ({m['id']})")
                
                choice = input(f"\nSelect a contact (1-{len(matches[:5])}) or 'n' to cancel: ").strip().lower()
                
                if choice == 'n':
                    return "❌ Action cancelled by user."
                
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(matches[:5]):
                        selected_match = matches[idx]
                        
                        # Confirm Selection
                        print(f"✅ You selected: {selected_match['name']}")
                        confirm_final = input(f"Confirm send to {selected_match['name']}? (y/n): ").strip().lower()
                        
                        if confirm_final == 'y':
                            target_id = selected_match['id']
                            confirmed = True
                            
                            # SAVE ALIAS HERE
                            # We allow the user to refer to this ID by the original 'phone' input next time
                            from .contacts import save_contact_alias
                            print(f"[System] Saving alias for future use...")
                            save_contact_alias(phone, selected_match['name'], target_id)
                            
                            break
                        else:
                            print("❌ Selection cancelled.")
                            continue # Try again

                print("❌ Invalid selection. Please try again.")

            if not confirmed:
                 return "❌ Could not verify recipient. Aborting."

    # --- Step 2: Send Message ---
    try:
        url = f"{BASE_URL}/api/sendText"
        payload = {
            "session": session_name,
            "chatId": target_id,
            "text": message
        }
        
        headers = get_headers()
        response = requests.post(url, json=payload, headers=headers)
        
        # Success Case
        if response.status_code == 201:
            return f"✅ Message sent to {target_id}"
        
        # Handle 'Session Stopped' Error automatically
        if "STOPPED" in response.text:
            print("[System] Session stopped. Restarting...")
            start_session(session_name)
            # Retry sending once
            time.sleep(3) 
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                return f"✅ Message sent (after restart) to {target_id}"
        
        return f"❌ Failed to send: {response.text}"
        
    except requests.exceptions.ConnectionError:
        print("[System] Connection failed. WAHA Container might be down. Starting it now...")
        from .manage import start_waha
        start_waha()
        
        # Wait for server to come online
        print("[System] Waiting for WAHA to start...")
        for _ in range(15):  # Wait up to 30 seconds
            try:
                if requests.get(f"{BASE_URL}/api/sessions", headers=get_headers()).status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                time.sleep(2)
        else:
            return "❌ Error: Could not start WAHA Server (Timeout)."

        # Check and Start Session
        print("[System] Checking session status...")
        from .session import get_status
        status_msg = get_status(session_name)
        
        if "STOPPED" in status_msg or "Session not found" in status_msg:
            print("[System] Session is stopped. Starting session...")
            start_session(session_name)
            time.sleep(5) # Wait for session to spin up
        
        # Retry sending
        try:
            print("[System] Retrying message send...")
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                return f"✅ Message sent (after server start) to {target_id}"
            return f"❌ Failed to send after restart: {response.text}"
        except Exception as e:
            return f"❌ Error after restart: {e}"

    except Exception as e:
        return f"❌ Error: {e}"
