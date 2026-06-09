import os
import sys
from ytmusicapi import YTMusic

def main():
    print("====================================================")
    print("        YouTube Music API Authentication Setup      ")
    print("====================================================")
    print("To authenticate ytmusicapi, we need your session headers from Brave.")
    print("Follow these steps:")
    print("1. Open Brave and go to https://music.youtube.com")
    print("2. Ensure you are signed into your YouTube Premium/Google account.")
    print("3. Press F12 to open Developer Tools, and click the 'Network' tab.")
    print("4. Refresh the page.")
    print("5. In the list of requests, search for 'browse' (or any document request).")
    print("6. Click on it, look at the 'Request Headers' section.")
    print("7. Copy all request headers (everything starting from 'accept: ...' or 'Cookie: ...').")
    print("====================================================\n")
    
    print("Paste the copied headers here (press Ctrl+D on a new line when finished):")
    
    headers_lines = []
    try:
        while True:
            line = input()
            headers_lines.append(line)
    except EOFError:
        pass
        
    headers_raw = "\n".join(headers_lines)
    if not headers_raw.strip():
        print("Error: No headers pasted.")
        sys.exit(1)
        
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
    os.makedirs(config_dir, exist_ok=True)
    auth_path = os.path.join(config_dir, "ytmusic_headers.json")
    
    try:
        # Generate the auth file from the raw headers pasted
        YTMusic.setup(filepath=auth_path, headers_raw=headers_raw)
        print(f"\n✅ Success! YouTube Music authentication saved to: {auth_path}")
        print("You can now query and manage your library programmatically!")
    except Exception as e:
        print(f"\n❌ Error setting up authentication: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
