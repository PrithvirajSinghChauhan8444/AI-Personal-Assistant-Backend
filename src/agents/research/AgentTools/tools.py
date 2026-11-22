"""Consolidated Tool Definitions & Local Implementations for ResearchAgent.

All research tools (both Go-native contracts and in-process Python tools)
are defined and managed in this single file.
"""

from __future__ import annotations

import ast
import operator
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.agents.contracts import ToolDefinition

# Registry mapping: tool_name -> (ToolDefinition, Optional[Callable])
RESEARCH_TOOLS_REGISTRY: Dict[str, Tuple[ToolDefinition, Optional[Callable]]] = {}


def register_research_tool(
    name: str,
    category: str,
    description: str,
    risk: str = "LOW",
    prompt_usage_tip: str = "",
    parameters: Optional[Dict[str, Any]] = None,
    execution_domain: str = "python_local",
    required_capability: str = "",
) -> Callable[[Optional[Callable]], Optional[Callable]]:
    """Decorator to declare and register a research tool."""
    def decorator(fn: Optional[Callable] = None) -> Optional[Callable]:
        tool_def = ToolDefinition(
            name=name,
            category=category,
            description=description,
            risk=risk,
            prompt_usage_tip=prompt_usage_tip,
            parameters=parameters or {"type": "object", "properties": {}},
            execution_domain=execution_domain,
            required_capability=required_capability,
        )
        RESEARCH_TOOLS_REGISTRY[name] = (tool_def, fn)
        return fn

    return decorator


# ============================================================================
# 1. Local Python Research Tools (Execution Domain: python_local)
# ============================================================================

_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_math(node: ast.AST) -> float | int:
    """Safely evaluates an arithmetic AST node without arbitrary code execution."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in _SAFE_OPERATORS:
            left = _safe_eval_math(node.left)
            right = _safe_eval_math(node.right)
            return _SAFE_OPERATORS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in _SAFE_OPERATORS:
            return _SAFE_OPERATORS[op_type](_safe_eval_math(node.operand))
    raise ValueError(f"Unsupported math syntax: {ast.dump(node)}")


@register_research_tool(
    name="research_calculate",
    category="research",
    description="Performs safe, in-process mathematical calculations (fractions, percentages, statistics) for research data.",
    risk="LOW",
    prompt_usage_tip="Use for quick arithmetic, percentage deltas, or scientific calculation without invoking shell commands.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Mathematical expression (e.g. '(1500 - 1200) / 1200 * 100')"},
        },
        "required": ["expression"],
    },
    execution_domain="python_local",
    required_capability="research:calc",
)
def research_calculate(expression: str) -> str:
    """Evaluates mathematical expression safely in Python."""
    cleaned = expression.strip()
    if not cleaned:
        return "Error: empty expression provided"
    try:
        parsed = ast.parse(cleaned, mode="eval")
        result = _safe_eval_math(parsed.body)
        return str(result)
    except Exception as exc:
        return f"Error evaluating expression '{cleaned}': {exc}"


@register_research_tool(
    name="research_extract_keywords",
    category="research",
    description="Extracts key technical terms, entities, and frequent topics from research texts or article snippets.",
    risk="LOW",
    prompt_usage_tip="Use to distill search results or long texts into concise search tags and key concepts.",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text body to analyze"},
            "top_k": {"type": "integer", "description": "Maximum number of keywords to return (default: 5)", "default": 5},
        },
        "required": ["text"],
    },
    execution_domain="python_local",
    required_capability="research:nlp",
)
def research_extract_keywords(text: str, top_k: int = 5) -> str:
    """Extracts non-stopword frequent terms from text locally in Python."""
    if not text or not text.strip():
        return "Error: text cannot be empty"

    words = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower())
    stopwords = {
        "the", "and", "for", "that", "this", "with", "from", "are", "was",
        "were", "have", "has", "had", "which", "they", "been", "their", "will",
        "would", "could", "should", "what", "when", "where", "about", "into",
    }
    filtered = [w for w in words if w not in stopwords]
    counts: Dict[str, int] = {}
    for word in filtered:
        counts[word] = counts.get(word, 0) + 1

    sorted_words = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top_words = [f"{w} ({c})" for w, c in sorted_words[:top_k]]
    return ", ".join(top_words) if top_words else "No distinctive keywords found"


@register_research_tool(
    name="research_format_citations",
    category="research",
    description="Formats raw research URLs, titles, and snippets into standard bibliography citations (Markdown or APA style).",
    risk="LOW",
    prompt_usage_tip="Use to generate clean source citations for user answers.",
    parameters={
        "type": "object",
        "properties": {
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "author": {"type": "string"},
                    },
                    "required": ["title", "url"],
                },
                "description": "List of source objects containing title and url",
            },
            "style": {"type": "string", "enum": ["markdown", "inline"], "default": "markdown"},
        },
        "required": ["sources"],
    },
    execution_domain="python_local",
    required_capability="research:format",
)
def research_format_citations(sources: List[Dict[str, Any]], style: str = "markdown") -> str:
    """Formats list of sources into citations."""
    if not sources:
        return "No sources provided"

    citations = []
    for idx, s in enumerate(sources, 1):
        title = s.get("title", "Untitled Source").strip()
        url = s.get("url", "").strip()
        author = s.get("author", "").strip()
        author_str = f"{author.rstrip('.')}. " if author else ""
        if style == "inline":
            citations.append(f"[{idx}] {author_str}{title} ({url})")
        else:
            citations.append(f"{idx}. {author_str}[{title}]({url})")
    return "\n".join(citations)


# ============================================================================
# 2. Go-Native Research Tools (Execution Domain: go_native)
# ============================================================================

register_research_tool(
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
    execution_domain="go_native",
    required_capability="net:read",
)()

register_research_tool(
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
    execution_domain="go_native",
    required_capability="net:read",
)()

register_research_tool(
    name="net_weather",
    category="net",
    description="Fetches current weather conditions and temperature for a given city or location.",
    risk="LOW",
    prompt_usage_tip="Use to answer queries about current weather, temperature, or forecasts.",
    parameters={
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City name or location (e.g. 'London', 'Agra', 'Tokyo')"},
            "format": {"type": "string", "enum": ["summary", "detailed"], "description": "Format: 'summary' or 'detailed'", "default": "summary"},
        },
        "required": ["location"],
    },
    execution_domain="go_native",
    required_capability="net:read",
)()

# ============================================================================
# 3. Layer 5 Memory & MCP Tools (Specialized Domains)
# ============================================================================

register_research_tool(
    name="memory_search",
    category="memory",
    description="Searches long-term episodic and semantic memory for relevant facts, profiles, and past answers.",
    risk="LOW",
    prompt_usage_tip="Use to recall user preferences, project details, or historical answers.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Semantic search query string"},
            "top_k": {"type": "integer", "description": "Maximum memory records to return (default: 5)", "default": 5},
            "category": {
                "type": "string",
                "enum": ["project", "system", "conversation", "note"],
                "description": "Optional category filter",
            },
        },
        "required": ["query"],
    },
    execution_domain="python_local",
    required_capability="memory",
)()

register_research_tool(
    name="memory_store_fact",
    category="memory",
    description="Persists an important fact, user preference, or research finding into long-term memory.",
    risk="MEDIUM",
    prompt_usage_tip="Use to remember user instructions, key facts, or summarized research conclusions.",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Factual statement or note to remember (or 'fact')"},
            "category": {
                "type": "string",
                "enum": ["project", "system", "conversation", "note"],
                "description": "Classification category (default: note)",
                "default": "note",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional searchable keywords",
            },
        },
        "required": ["content"],
    },
    execution_domain="python_local",
    required_capability="memory",
)()

register_research_tool(
    name="youtube__get_transcript",
    category="mcp",
    description="Fetches the full spoken transcript of a YouTube video given its URL or ID.",
    risk="LOW",
    prompt_usage_tip="Use when user provides a YouTube link or asks to summarize a video.",
    parameters={
        "type": "object",
        "properties": {
            "url_or_id": {"type": "string", "description": "YouTube video URL or 11-char ID"},
            "include_timestamps": {"type": "boolean", "description": "Whether to prepend timestamps to transcript lines", "default": False},
            "languages": {"type": "array", "items": {"type": "string"}, "description": "List of language codes to try in preference order (default: ['en'])", "default": ["en"]},
        },
        "required": ["url_or_id"],
    },
    execution_domain="mcp_bridge",
    required_capability="mcp:youtube",
)()

register_research_tool(
    name="youtube__get_video_info",
    category="mcp",
    description="Retrieves metadata for a YouTube video: title, channel, duration, and view count.",
    risk="LOW",
    prompt_usage_tip="Use to inspect video details or author channel without loading full transcript.",
    parameters={
        "type": "object",
        "properties": {
            "url_or_id": {"type": "string", "description": "YouTube video URL or 11-char ID"},
        },
        "required": ["url_or_id"],
    },
    execution_domain="mcp_bridge",
    required_capability="mcp:youtube",
)()

register_research_tool(
    name="youtube__search_videos",
    category="mcp",
    description="Searches YouTube for videos matching a query keyword and returns titles, channels, and URLs.",
    risk="LOW",
    prompt_usage_tip="Use when finding relevant video references or tutorials on a topic.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword or topic"},
            "max_results": {"type": "integer", "description": "Maximum videos to return (1-10, default: 5)", "default": 5},
        },
        "required": ["query"],
    },
    execution_domain="mcp_bridge",
    required_capability="mcp:youtube",
)()


# ============================================================================
# Dynamic Discovery & Export Functions
# ============================================================================

def get_research_tools() -> Dict[str, Tuple[ToolDefinition, Optional[Callable]]]:
    """Returns all registered research tools with their definitions and callables."""
    return dict(RESEARCH_TOOLS_REGISTRY)


def get_research_tool_definitions() -> List[ToolDefinition]:
    """Returns a list of all ToolDefinition instances for the Research Agent."""
    return [t_def for t_def, _ in RESEARCH_TOOLS_REGISTRY.values()]


def get_research_local_handlers() -> Dict[str, Callable]:
    """Returns all active in-process Python callable handlers for Research Agent."""
    return {
        name: fn
        for name, (_, fn) in RESEARCH_TOOLS_REGISTRY.items()
        if fn is not None
    }


def enrich_prompt_with_tools(base_prompt: str, tools: List[ToolDefinition]) -> str:
    """Enriches the agent's base system prompt with dynamic tool capability tips."""
    tool_tips = "\n".join([
        f"- **`{t.name}`** [{t.execution_domain} | {t.risk}]: {t.prompt_usage_tip or t.description}"
        for t in tools
    ])
    header = "\n\n### Dynamically Injected Tools & Capabilities\n"
    return f"{base_prompt.rstrip()}{header}{tool_tips}\n"


# Expose standard RESEARCH_TOOLS list for backwards compatibility
RESEARCH_TOOLS = get_research_tool_definitions()
