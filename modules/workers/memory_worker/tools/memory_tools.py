from typing import Any
from langchain_core.tools import tool
from modules.workers.memory_worker.integrations.memory_client import (
    remember_fact as _remember,
    recall_fact as _recall,
    forget_fact as _forget,
    search_chat as _search_chat,
    search_skills as _search_skills,
    update_skill_content as _update_skill
)

@tool
def remember_tool(key: str, value: Any, category: str = "past") -> str:
    """Saves a key-value fact, preference, or datum into long-term memory."""
    return _remember(key=key, value=value, category=category)

@tool
def recall_tool(key: str, category: str = "past") -> str:
    """Retrieves a previously stored memory by key."""
    return _recall(key=key, category=category)

@tool
def forget_tool(key: str, category: str = "past") -> str:
    """Deletes a memory key from long-term memory."""
    return _forget(key=key, category=category)

@tool
def search_chat_tool(query: str, limit: int = 5) -> str:
    """Searches past conversation logs and chat turns."""
    return _search_chat(query=query, limit=limit)

@tool
def search_skills_tool(query: str) -> str:
    """Searches agent skills and custom execution instructions."""
    return _search_skills(query=query)

@tool
def update_skill_tool(skill_name: str, content: str) -> str:
    """Updates or creates a learned skill Markdown definition."""
    return _update_skill(skill_name=skill_name, content=content)

memory_tools = [
    remember_tool,
    recall_tool,
    forget_tool,
    search_chat_tool,
    search_skills_tool,
    update_skill_tool
]
