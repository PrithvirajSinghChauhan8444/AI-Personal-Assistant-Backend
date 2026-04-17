from Apps.SystemControl.execution import launch_app
import time

print("--- Test 1: Direct App Launch (AppOpener) ---")
# 'notepad' -> Should use AppOpener
# CAUTION: This will actually open notepad.
res1 = launch_app("notepad")
print(res1)

print("\n--- Test 2: File Launch (Subprocess) ---")
# 'notepad' + arg -> Should use Subprocess
res2 = launch_app("notepad", "task.md")
print(res2)

print("\n--- Test 3: Path Alias (Explorer) ---")
# Assuming 'projects' is in important_paths.json
# If not, add a temp alias or test non-alias fallback?
# let's try a known path if available, or just mock?
# I'll rely on existing behavior.
res3 = launch_app("projects") 
print(res3)
