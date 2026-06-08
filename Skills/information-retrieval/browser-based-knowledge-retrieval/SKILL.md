---
name: browser-based-knowledge-retrieval
description: "A generalized workflow for using a browser agent to search the web for a topic, navigate to relevant articles, read their content, and extract structured data (like features and pricing) from multiple sources."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: information-retrieval
    tags: []
---
# Browser Based Knowledge Retrieval

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
*   **Search:** Use the browser agent to search Google for the target query to find relevant articles.
*   **Navigation:** Identify the top N relevant articles from the search results.
*   **Extraction:** Systematically visit each article, read the content, and extract specific required data points (e.g., features, pricing) into a structured format.
*   **Consolidation:** Aggregate all extracted data from the sources into a single, structured output.
*   **Storage:** Save the final structured data into a specified file format (e.g., JSON) within the workspace.