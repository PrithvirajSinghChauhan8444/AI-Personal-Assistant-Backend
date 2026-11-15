"""Tool definitions and schemas for Layer 5 Memory Layer."""

from typing import List

from src.agents.contracts import ToolDefinition

MEMORY_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="memory_update_profile",
        category="memory",
        description="Add, modify, or delete a core user preference, personal rule, or identity attribute in core_profile.md.",
        risk="LOW",
        prompt_usage_tip="Use when the user explicitly expresses a permanent preference, communication style, or personal rule.",
        parameters={
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": "Section header in core_profile.md (e.g. 'Identity', 'Preferences and Rules', 'Personal Context')",
                },
                "key": {"type": "string", "description": "Preference name or rule title"},
                "value": {"type": "string", "description": "New rule text or value (pass empty string to delete)"},
            },
            "required": ["section", "key", "value"],
        },
    ),
    ToolDefinition(
        name="memory_update_account",
        category="memory",
        description="Add, update, or remove a connected user account or email alias in accounts.md.",
        risk="LOW",
        prompt_usage_tip="Use when the user shares or updates an email address, account alias (e.g. 'email1', 'email2', or custom label), or communication handle.",
        parameters={
            "type": "object",
            "properties": {
                "alias": {
                    "type": "string",
                    "description": "Account alias (e.g. 'email1', 'email2', or custom label; omit to auto-assign next arbitrary alias)",
                },
                "email": {
                    "type": "string",
                    "description": "Email address associated with this account (pass empty string to delete)",
                },
                "provider": {
                    "type": "string",
                    "description": "Provider type (default: google)",
                    "default": "google",
                },
            },
            "required": ["email"],
        },
    ),
    ToolDefinition(
        name="memory_store_fact",
        category="memory",
        description="Commit an archival fact, note, or historical detail with vector embedding into long-term memory.",
        risk="LOW",
        prompt_usage_tip="Use to remember durable facts, personal notes, or summarized discoveries for future turns.",
        parameters={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The atomic fact or note snippet to store"},
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
    ),
    ToolDefinition(
        name="memory_search",
        category="memory",
        description="Search long-term episodic and semantic memory using local vector similarity.",
        risk="LOW",
        prompt_usage_tip="Use to recall user preferences, historical notes, or past facts relevant to the current task.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language semantic search query"},
                "category": {
                    "type": "string",
                    "description": "Optional category filter (project, system, conversation, note)",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum matching snippets to return (default: 3)",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="memory_delete",
        category="memory",
        description="Delete a long-term memory chunk by ID to eliminate contradictions or outdated facts.",
        risk="MEDIUM",
        prompt_usage_tip="Use when an existing memory is identified as contradicted, obsolete, or explicitly forgotten by the user.",
        parameters={
            "type": "object",
            "properties": {
                "memory_id": {"type": "string", "description": "UUID of the episodic memory record to delete"},
                "reason": {"type": "string", "description": "Optional reason for deletion audit"},
            },
            "required": ["memory_id"],
        },
    ),
]
