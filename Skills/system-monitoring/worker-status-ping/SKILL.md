---
name: worker-status-ping
description: "A generalized procedure for checking the operational status of all known system workers."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: system-monitoring
    tags: []
---
# Worker Status Ping

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Identify all known system workers (e.g., SystemWorker, ProductivityWorker, MemoryWorker, ClassroomWorker, GitHub Worker, etc.).
2. Iterate through the list of workers and execute a status check command for each one.
3. Aggregate and present the status information for all workers in a unified report.