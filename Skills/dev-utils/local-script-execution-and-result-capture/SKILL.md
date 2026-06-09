---
name: local-script-execution-and-result-capture
description: "A generalized procedure for executing local Python scripts from a specified path with arguments and capturing the JSON output for subsequent use."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: dev-utils
    tags: []
---
# Local Script Execution And Result Capture

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Identify the exact path to the target Python script (e.g., `/path/to/script.py`).
2. Invoke the script using the Python interpreter (e.g., `python3 /path/to/script.py arg1 arg2`).
3. Capture the standard output or return value, which is expected to be in JSON format.
4. Store the captured result for later analysis or memory storage.