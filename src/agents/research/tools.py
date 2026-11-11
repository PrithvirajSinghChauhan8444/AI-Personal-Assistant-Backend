"""Tool definitions for ResearchAgent."""

from typing import List

from src.agents.contracts import ToolDefinition

RESEARCH_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="net_search",
        category="net",
        description="Queries web search engines to retrieve relevant search snippets, titles, and URLs.",
        risk="LOW",
        prompt_usage_tip="Use to find live documentation, news, facts, and external references.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords or question"},
                "limit": {"type": "integer", "description": "Maximum results to return (default: 10)", "default": 10},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="net_fetch",
        category="net",
        description="Executes high-speed HTTP requests with custom headers and response inspection.",
        risk="LOW",
        prompt_usage_tip="Use to fetch web pages, raw markdown, or REST API endpoints.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target HTTP/HTTPS URL"},
                "method": {"type": "string", "description": "HTTP method (default: GET)", "default": "GET"},
                "headers": {"type": "object", "description": "Optional HTTP headers"},
                "body": {"type": "string", "description": "Optional request body"},
                "timeout_seconds": {"type": "integer", "description": "Timeout in seconds (default: 15)", "default": 15},
            },
            "required": ["url"],
        },
    ),
    ToolDefinition(
        name="memory_search",
        category="memory",
        description="Searches long-term episodic and semantic memory for relevant facts, profiles, and past answers.",
        risk="LOW",
        prompt_usage_tip="Use to recall user preferences, project details, or historical answers.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Semantic search query string"},
                "limit": {"type": "integer", "description": "Maximum memory records to return (default: 5)", "default": 5},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="memory_store_fact",
        category="memory",
        description="Persists an important fact, user preference, or research finding into long-term memory.",
        risk="MEDIUM",
        prompt_usage_tip="Use to remember user instructions, key facts, or summarized research conclusions.",
        parameters={
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "Factual statement or note to remember"},
                "category": {"type": "string", "description": "Category tag (e.g. user_preference, tech_spec, meeting_note)"},
            },
            "required": ["fact"],
        },
    ),
]
