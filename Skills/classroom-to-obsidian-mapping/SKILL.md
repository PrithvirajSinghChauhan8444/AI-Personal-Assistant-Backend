---
name: classroom-to-obsidian-mapping
description: "A multi-step process to retrieve structured course data and successfully map it into a user's Obsidian vault, preparing it for visualization."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: File System & Knowledge Base Management
    tags: ["obsidian", "classroom", "data_extraction", "workflow"]
---
# Classroom To Obsidian Mapping

## When to Use
Use this skill when you need to execute workflows related to obsidian, classroom, data_extraction, workflow.

## Procedure
1. **Data Retrieval:** Initiate a request to retrieve a structured list of active Google Classroom courses and their associated assignments for the user's profile.
2. **Data Structuring:** Parse the retrieved data to extract key course names and specific assignment deadlines.
3. **Vault Integration:** Execute a nested Obsidian sub-plan to categorize and commit the extracted coursework data into the user's specified Obsidian vault structure.
4. **Visualization Preparation:** Present the structured data in a clear, tabular format, making it ready for direct import or visualization within the Obsidian environment (e.g., using Dataview or graph views).