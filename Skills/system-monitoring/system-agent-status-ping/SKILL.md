---
name: system-agent-status-ping
description: "A generalized procedure for querying the operational status of all integrated system agents."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: system-monitoring
    tags: []
---
# System Agent Status Ping

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Initiate a broadcast command to all integrated system agents to request their current operational status.
2. Aggregate the status reports returned by each agent.
3. Compile the individual status reports into a unified, readable report format for the user, highlighting the readiness of each agent.