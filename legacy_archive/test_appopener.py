from AppOpener import open as open_app
import time

print("Opening Notepad...")
open_app("notepad")
time.sleep(2)
print("Finished opening notepad.")

# Test with args
# Create a dummy file
with open("test_file.txt", "w") as f:
    f.write("Hello AppOpener")

print("Opening Notepad with arg...")
try:
    # Try passing as single string?
    open_app("notepad test_file.txt") 
except Exception as e:
    print(f"Error with arg: {e}")
