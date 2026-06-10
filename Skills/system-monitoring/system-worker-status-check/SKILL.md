---
name: system-worker-status-check
description: "Performs a comprehensive status check across all known system workers (SystemWorker, ProductivityWorker, GitHubWorker, ClassroomWorker, GmailWorker, MiscWorker, BrowserWorker) by simulating a system-wide ping test."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: system-monitoring
    tags: []
---
# System Worker Status Check

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Execute the internal `worker-status-ping` procedure to initiate a connectivity check across all registered workers.
2. Analyze the results to compile a summary of the operational status for each worker.
3. Report the final status, noting any specific failures or operational details for each component.