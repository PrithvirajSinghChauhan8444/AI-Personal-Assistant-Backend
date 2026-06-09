---
name: system-process-status-and-launch
description: "A generalized procedure for checking the status of a running application and launching it if it is not running, using system commands."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: system-management
    tags: []
---
# System Process Status And Launch

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Attempt to check the status of the target application using appropriate system tools (e.g., `ps`, `pgrep`, or service status commands). 2. If the application is not found or not running, execute the appropriate system command (e.g., `systemctl start <service_name>` or direct executable launch) to start the application. 3. Verify the application's status post-execution to confirm it is running.