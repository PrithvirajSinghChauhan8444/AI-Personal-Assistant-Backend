import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from Apps.SystemControl.execution import launch_app

print("Attempting to launch spotify...")
try:
    result = launch_app("spotify")
    print(result)
except Exception as e:
    print(f"Reproduction Failed (Exception caught): {e}")
