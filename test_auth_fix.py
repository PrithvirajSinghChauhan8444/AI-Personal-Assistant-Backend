import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath("src"))

# Mock input to avoid blocking
from unittest.mock import patch

from CoreFunctions.auth_utils import verify_password

# We mock input to simulate user typing "password"
# Note: This assumes AGENT_PASSWORD is set or we just want to see if it crashes before input.
# If it crashes reading .env, it happens before input.

print("Testing verify_password encoding safety...")
try:
    # We patch input just in case it reaches that point (which means success!)
    with patch('builtins.input', return_value="anything"):
        verify_password()
    print("✅ verify_password executed without crashing (Success!)")
except Exception as e:
    print(f"❌ Failed: {e}")
