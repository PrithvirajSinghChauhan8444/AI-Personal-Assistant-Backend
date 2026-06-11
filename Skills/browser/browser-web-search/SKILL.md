---
name: browser-web-search
description: "Instructions for navigating a browser to perform web searches, click result links, and extract content."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: browser
    tags: ["search", "web-search", "scrape", "browse"]
---
# Browser Web Search

## When to Use
Use this skill when you need to perform active, real-time web searches using the browser agent, click on search result links, navigate pages, and scrape information. This is useful when the simple duckduckgo API tool is insufficient or blocked, or when you need to read specific websites dynamically.

## Procedure
1. **Navigate to the Search Engine**:
   * Call `browser_navigate` with the URL: `https://duckduckgo.com` (preferred) or `https://google.com`.
2. **Perform the Search Query**:
   * Inspect the returned interactive elements for the search input box (usually an input element with text placeholder like "Search the web" or selector `input[name="q"]`).
   * Call `browser_input` (passing the text box `element_id` or using `browser_input_selector` with `input[name="q"]`) and input the user's search query.
   * Submit the search by clicking the search button or pressing Enter.
3. **Analyze Search Results**:
   * Call `browser_read_current_page` to check the search results links.
   * Find the most relevant search result title. Inspect the element IDs corresponding to the result links.
4. **Visit the Target Website**:
   * Call `browser_click` on the element ID corresponding to the chosen result link (or use `browser_click_selector` with the link anchor selector).
   * Wait for the page to load.
5. **Read Page Content**:
   * Use `browser_read_page_content` to extract text from the website.
   * Recommend using `mode="query"` to ask a specific question, or `mode="summary"` for summaries.
