
import sys
import os

# Fix path to include src (two levels up from src/Apps/WhatsApp)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from Apps.WhatsApp.contacts import resolve_to_number, save_contacts_local, load_contacts_local

def test_contacts():
    print("1. Testing Save/Load local...")
    test_data = [{"name": "Test User", "id": "1234567890@c.us"}]
    save_contacts_local(test_data)
    
    loaded = load_contacts_local()
    if loaded == test_data:
        print("✅ Save/Load Successful")
    else:
        print("❌ Save/Load Failed")
        print(f"Expected: {test_data}")
        print(f"Got: {loaded}")

    print("\n2. Testing Resolution (Local)...")
    matches = resolve_to_number("Test User")
    if matches and matches[0]['id'] == "1234567890@c.us":
        print("✅ Resolution 'Test User' -> Found")
    else:
        print("❌ Resolution 'Test User' -> Failed")
        print(matches)

    print("\n3. Testing Direct ID...")
    matches = resolve_to_number("919999999999@c.us")
    if matches and matches[0]['type'] == 'direct':
        print("✅ Direct ID detection successful")
    else:
        print("❌ Direct ID detection failed")

    print("\n4. Testing Typos (AI-like search)...")
    # 'Tst User' should match 'Test User' with difflib
    matches = resolve_to_number("Tst User")
    if matches and matches[0]['id'] == "1234567890@c.us":
        print(f"✅ Typo Resolution 'Tst User' -> Found: {matches[0]['name']}")
    else:
        print("❌ Typo Resolution 'Tst User' -> Failed")
        print(matches)

if __name__ == "__main__":
    try:
        test_contacts()
        print("\nVerification Script Completed.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
