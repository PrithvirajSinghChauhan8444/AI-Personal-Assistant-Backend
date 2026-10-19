import os
import sys
import threading
from typing import Optional

# Global stdin/stdout mutex lock for serializing interactive console inputs
_console_lock = threading.RLock()

def get_console_lock() -> threading.RLock:
    return _console_lock

def verify_password(prompt_reason: str = "Execute critical action") -> bool:
    """Prompts the user for authorization password under thread-safe console lock."""
    configured_password = os.environ.get("SYSTEM_PASSWORD", "").strip()
    if not configured_password:
        return True  # No password configured, bypass check

    with _console_lock:
        print("\n" + "=" * 50)
        print(f"🔒 [Security Gateway Challenge]")
        print(f"Action: {prompt_reason}")
        print("=" * 50)
        try:
            import getpass
            attempt = getpass.getpass("Enter System Password: ")
            if attempt.strip() == configured_password:
                print("✔ Authorization verified.\n")
                return True
            else:
                print("❌ Invalid password. Action denied.\n")
                return False
        except (KeyboardInterrupt, EOFError):
            print("\n❌ Authorization aborted.")
            return False
