import sys
import os

# Add src to sys.path
sys.path.append(os.path.abspath("src"))

from CoreFunctions.tools import get_time, check_calendar_events

print("--- Testing get_time ---")
get_time()

print("\n--- Testing check_calendar_events ---")
try:
    check_calendar_events(max_results=1)
except Exception as e:
    print(f"Calendar check failed (expected if creds missing): {e}")

print("\n--- Test Complete ---")
