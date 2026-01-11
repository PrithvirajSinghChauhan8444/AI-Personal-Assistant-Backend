import sys
import os
import json
import os
import requests
import difflib
from .config import BASE_URL, get_headers

CONTACTS_FILE = os.path.join(os.path.dirname(__file__), "contacts.json")

def load_aliases():
    """Loads the cached aliases from contacts.json."""
    if not os.path.exists(CONTACTS_FILE):
        return []
    try:
        with open(CONTACTS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_contact_alias(referred_name, contact_name, contact_id):
    """
    Saves a new alias mapping to contacts.json.
    referred_name: The name the user used (e.g., 'ABCD')
    contact_name: The actual WhatsApp name (e.g., 'Abc Def')
    contact_id: The WhatsApp ID
    """
    aliases = load_aliases()
    
    # Check if already exists to avoid duplicates
    for alias in aliases:
        if alias.get('referred', '').lower() == referred_name.lower():
            # Update existing if needed, or just return
            alias['name'] = contact_name
            alias['id'] = contact_id
            break
    else:
        # Add new
        aliases.append({
            "referred": referred_name,
            "name": contact_name,
            "id": contact_id
        })
    
    with open(CONTACTS_FILE, 'w') as f:
        json.dump(aliases, f, indent=4)
    print(f"[System] Saved alias: '{referred_name}' -> {contact_name}")

def resolve_to_number(identifier, session_name="default"):
    """
    Resolves an identifier to a list of potential contact matches.
    1. Checks for direct ID.
    2. Checks local alias cache (contacts.json) - Exact match on 'referred'.
    3. If no cache match, searches online (WAHA) - Fuzzy match.
    """
    identifier = str(identifier).strip()
    
    # 1. Check Direct ID
    if "@" in identifier:
         return [{'name': 'Direct ID', 'id': identifier, 'type': 'direct'}]

    # 2. Check Local Alias Cache
    aliases = load_aliases()
    for alias in aliases:
        if alias.get('referred', '').lower() == identifier.lower():
            # Found a saved alias!
            return [{
                'name': alias['name'],
                'id': alias['id'],
                'referred': alias['referred'],
                'source': 'cache'
            }]

    # 3. Online Search (WAHA) if not in cache
    print(f"🔎 '{identifier}' not in cache. Searching WhatsApp contacts online...")
    contacts_list = []
    try:
        url = f"{BASE_URL}/api/contacts/all?session={session_name}"
        response = requests.get(url, headers=get_headers())
        if response.status_code != 200:
            print(f"Error fetching contacts: {response.text}")
            return []
        contacts_list = response.json()
    except Exception as e:
        print(f"Error connecting to WhatsApp API: {e}")
        return []

    # Fuzzy search logic
    query = identifier.lower()
    matches = []
    seen_ids = set()

    # Pre-process contacts for diff search
    # Map "normalized_name" -> contact_obj
    name_map = {} 
    
    for contact in contacts_list:
        c_name = contact.get('name') or contact.get('pushname') or ""
        raw_id = contact.get('id')
        if isinstance(raw_id, dict):
             c_id = raw_id.get('_serialized')
        else:
             c_id = raw_id
        
        if not c_id: continue
        if c_id in seen_ids: continue
        
        # Store for retrieval
        contact_entry = {
                "name": c_name or "Unknown",
                "id": c_id,
                "type": "contact"
        }
        
        if c_name:
            name_map[c_name.lower()] = contact_entry
        
        # Also check direct number match
        if query in c_id.replace('@c.us',''):
            matches.append({**contact_entry, "score": 90, "match_type": "number_partial"})
            seen_ids.add(c_id)

    # Use difflib to find close matches to the name
    # get_close_matches(word, possibilities, n, cutoff)
    # cutoff=0.4 means we allow quite a bit of typo
    close_names = difflib.get_close_matches(query, name_map.keys(), n=5, cutoff=0.4)
    
    for match_name in close_names:
        entry = name_map[match_name]
        if entry['id'] not in seen_ids:
            # Calculate a similarity score for sorting
            ratio = difflib.SequenceMatcher(None, query, match_name).ratio()
            matches.append({**entry, "score": int(ratio * 100), "match_type": "fuzzy_name"})
            seen_ids.add(entry['id'])

    # Sort by score desc
    return sorted(matches, key=lambda x: x['score'], reverse=True)

# Compatibility wrapper for existing tools
def get_contact_by_name(name_query, session_name="default"):
    matches = resolve_to_number(name_query, session_name)
    if not matches:
        return f"No contact found matching '{name_query}'."
    
    output = ["Found Contacts:"]
    for m in matches:
        output.append(f"Name: {m['name']} | ID: {m['id']}")
    return "\n".join(output)

if __name__ == "__main__":
    # Test
    print(resolve_to_number("Praveen"))