import os
import sys
import base64
import imaplib

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.CoreFunctions.Infrastructure.auth_utils import get_valid_credentials, load_google_accounts
from src.CoreFunctions.Integrations.Gmail.gmail_idle_daemon import generate_xoauth2_string

def test_imap_connection(account_alias="personal"):
    print(f"🔍 Starting IMAP XOAUTH2 connection test for account '{account_alias}'...")
    try:
        # Load account email
        accounts = load_google_accounts()
        email = accounts.get(account_alias)
        if not email:
            print(f"❌ Account '{account_alias}' is not configured in google_accounts.json")
            return False
            
        print(f"📧 Resolved Email: {email}")
        
        # Load credentials
        creds = get_valid_credentials(account_alias)
        if not creds:
            print("❌ Failed to retrieve valid credentials.")
            return False
            
        print("🔑 Successfully loaded OAuth credentials. Fetching access token...")
        access_token = creds.token
        
        # Connect to Gmail IMAP
        print("🔌 Connecting to imap.gmail.com:993...")
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        
        # Generate XOAUTH2 token (raw bytes expected by imaplib callback)
        xoauth_raw = generate_xoauth2_string(email, access_token)
        
        # Authenticate (imaplib will automatically base64 encode this raw string)
        print("🔒 Authenticating via SASL XOAUTH2...")
        imap.authenticate('XOAUTH2', lambda x: xoauth_raw.encode('utf-8'))
        print("✅ Authentication successful!")
        
        # Select INBOX
        print("📂 Selecting INBOX...")
        status, messages = imap.select("INBOX")
        print(f"✅ INBOX select status: {status}, Total messages in folder: {messages[0].decode('utf-8')}")
        
        # Graceful logout
        imap.logout()
        print("🎉 All tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

if __name__ == "__main__":
    import sys
    account = sys.argv[1] if len(sys.argv) > 1 else "personal"
    success = test_imap_connection(account)
    sys.exit(0 if success else 1)
