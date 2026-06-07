---
name: github-profile-status-check
description: "Retrieves and summarizes the status of a specified GitHub user profile, including repository counts and profile details."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: GitHub Management
    tags: []
---
# Github Profile Status Check

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Call the `list_github_repos` tool for the target user to check for public repositories. 2. Retrieve the general profile information for the user. 3. Compile the results to report the account's status (e.g., number of repos, followers, and missing profile details).