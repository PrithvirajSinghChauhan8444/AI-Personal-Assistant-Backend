import requests
import time
import re
from datetime import datetime
from .config import BASE_URL, get_headers
from .contacts import resolve_to_number, save_contact_alias

def format_phone_number(phone):
    """
    Formats phone number to WAHA chat ID.
    - Removes non-digits.
    - Adds default country code '91' (India) if length is 10.
    """
    if "@" in str(phone):
        return phone

    clean_number = re.sub(r'\D', '', str(phone))
    
    if len(clean_number) == 10:
        clean_number = '91' + clean_number
    
    return f"{clean_number}@c.us"

def read_messages(chat_id_or_name, limit=10, session_name="default"):
    """
    Reads the last N messages from a WhatsApp chat.
    - chat_id_or_name: Name (e.g. 'Praveen') or ID ('123...').
    - limit: Number of messages to retrieve.
    """
    
    # --- Step 1: Resolve Contact ---
    target_id = None
    
    # Check if input is likely a Name or a Number
    is_likely_number = re.match(r'^\+?\d{10,15}$', str(chat_id_or_name)) or "@" in str(chat_id_or_name)
    
    if is_likely_number:
        target_id = format_phone_number(chat_id_or_name)
    else:
        # It's a name, let's resolve it
        print(f"🔍 Searching contact for: '{chat_id_or_name}'...")
        matches = resolve_to_number(chat_id_or_name, session_name)
        
        if not matches:
             return f"❌ Could not find any contact matching '{chat_id_or_name}'."
        
        target_id = None
        selected_match = None

        # Check for Cached Alias Match
        if len(matches) == 1 and matches[0].get('source') == 'cache':
            # It's a known alias!
            m = matches[0]
            print(f"✅ Found cached alias: '{m['referred']}' -> {m['name']} ({m['id']})")
            target_id = m['id']

        else:
            # Interactive Confirmation Loop for Online Search Results
            confirmed = False
            for attempt in range(3):
                print(f"\nFound {len(matches)} potential contacts for '{chat_id_or_name}':")
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
                        confirm_final = input(f"Confirm read messages from {selected_match['name']}? (y/n): ").strip().lower()
                        
                        if confirm_final == 'y':
                            target_id = selected_match['id']
                            confirmed = True
                            
                            # SAVE ALIAS HERE
                            print(f"[System] Saving alias for future use...")
                            save_contact_alias(chat_id_or_name, selected_match['name'], target_id)
                            
                            break
                        else:
                            print("❌ Selection cancelled.")
                            continue # Try again
                print("❌ Invalid selection. Please try again.")

            if not confirmed:
                 return "❌ Could not verify contact. Aborting."

    # --- Step 2: Fetch Messages ---
    try:
        url = f"{BASE_URL}/api/messages?chatId={target_id}&limit={limit}&session={session_name}"
        headers = get_headers()
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return f"❌ Failed to fetch messages: {response.text}"
            
        messages = response.json()
        
        if not messages:
            return f"No messages found in chat with {chat_id_or_name} ({target_id})."
            
        output = [f"--- Last {len(messages)} Messages with {chat_id_or_name} ---"]
        
        # Sort by timestamp just in case
        messages.sort(key=lambda x: x.get('timestamp', 0))
        
        for msg in messages:
            ts = msg.get('timestamp')
            dt_object = datetime.fromtimestamp(ts)
            time_str = dt_object.strftime('%Y-%m-%d %H:%M:%S')
            
            sender = "Me" if msg.get('fromMe') else "Them"
            content = msg.get('body', '[Media/No Body]')
            
            output.append(f"[{time_str}] {sender}: {content}")
            
        return "\n".join(output)

    except Exception as e:
        return f"❌ Error retrieving messages: {e}"

if __name__ == "__main__":
    # Test CLI
    search = input("Enter contact name or number to read: ")
    print(read_messages(search))
