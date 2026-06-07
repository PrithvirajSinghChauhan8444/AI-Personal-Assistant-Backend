---
name: github-repo-summary
description: "Retrieves and compiles a summary table of all public repositories for a specified GitHub user, including the repository name, primary language, and last update date."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: Code/Data Retrieval
    tags: ["github", "data_extraction", "summary"]
---
# Github Repo Summary

## When to Use
Use this skill when you need to execute workflows related to github, data_extraction, summary.

## Procedure
1. Identify the target GitHub user (e.g., PrithvirajSinghChauhan8444). 2. Execute a search or API call to retrieve the list of public repositories associated with that user. 3. For each repository found, extract the Repository Name, Language, and Last Updated date. 4. Format the extracted data into a readable Markdown table.