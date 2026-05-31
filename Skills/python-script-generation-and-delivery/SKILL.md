---
name: python-script-generation-and-delivery
description: "Generates a functional Python script based on a user request, includes input validation and error handling, and successfully delivers the resulting file to a specified email address."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: Software Development Workflow
    tags: []
---
# Python Script Generation And Delivery

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. **Generate Script:** Create a Python script that implements basic arithmetic operations (+, -, *, /) with robust input validation to prevent errors like division by zero. Ensure the script runs continuously until the user exits.
2. **Save Script:** Save the generated code to a designated file path (e.g., `CompiledScripts/calculator.py`).
3. **Delivery:** Send the content of the script to the user's specified personal email address.