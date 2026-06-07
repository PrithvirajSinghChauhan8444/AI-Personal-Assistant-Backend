---
name: github-repo-branch-and-latest-commit-analysis
description: "Analyzes a specified GitHub repository to list all local and remote branches, identify the most recently updated branch, and retrieve the details (commit message, date, SHA) of its latest update."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: Repository Analysis
    tags: []
---
# Github Repo Branch And Latest Commit Analysis

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Use the appropriate Git command (e.g., `git branch -a` or equivalent API call) to list all branches in the target repository. 2. Identify the branch with the most recent commit time (or the branch with the most recent push, depending on the required scope). 3. For the identified latest branch, retrieve the specific commit details using the corresponding SHA or reference (e.g., `git log -1 --format=format:...`). 4. Compile the list of branches and the details of the latest update into a structured response.