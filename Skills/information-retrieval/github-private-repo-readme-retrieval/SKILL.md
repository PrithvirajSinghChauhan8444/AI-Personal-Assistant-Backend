---
name: github-private-repo-readme-retrieval
description: "Retrieves the content of a specific file (like README.md) from a private GitHub repository branch, assuming necessary authentication context is provided."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: information-retrieval
    tags: []
---
# Github Private Repo Readme Retrieval

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Authenticate with the necessary GitHub credentials (e.g., via environment variables or token). 2. Specify the repository path and branch name (e.g., 'AI-Personal-Assistant-Backend/using-langgraph'). 3. Request the content of the target file (e.g., 'README.md') from that branch.