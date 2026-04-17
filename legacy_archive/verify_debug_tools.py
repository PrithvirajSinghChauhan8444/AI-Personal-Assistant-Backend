import sys
import os

# Ensure we can import from src
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from CoreFunctions.tools import AVAILABLE_TOOLS
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

print("--- Testing Debug Wrapper ---")

# Test 1: Simple Argument-less tool
print("\n> Testing 'get_time':")
if "get_time" in AVAILABLE_TOOLS:
    AVAILABLE_TOOLS["get_time"]()
else:
    print("get_time not found!")

# Test 2: Tool with Arguments (if possible without side effects)
# 'recall' is safe if key doesn't exist? or just verify function wrapped
print("\n> Testing wrapper on 'launch_app' (inspect only):")
if "launch_app" in AVAILABLE_TOOLS:
    func = AVAILABLE_TOOLS["launch_app"]
    print(f"Function name: {func.__name__}") # Should be 'launch_app_tool' (wrapped maintains name?) 
    # Actually functools.wraps maintains name, but let's see if we can trigger the print.
    # We won't actually launch app to avoid noise, just checking if it is wrapped.
    # But to see the print, we must call it.
    # Let's call a safe one like 'read_file' on a non-existent file?
    
print("\n> Testing 'read_file' with dummy path:")
if "read_file" in AVAILABLE_TOOLS:
    AVAILABLE_TOOLS["read_file"]("non_existent_file.txt")
