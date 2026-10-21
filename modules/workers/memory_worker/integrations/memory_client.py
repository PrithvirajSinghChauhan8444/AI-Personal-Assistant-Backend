from typing import Any, Dict, List, Optional
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import search_skills_vector

def remember_fact(key: str, value: Any, category: str = "past") -> str:
    try:
        store_memory(key=key, value=value, category=category)
        return f"Successfully saved memory '{key}' under category '{category}'."
    except Exception as e:
        return f"Error saving memory: {e}"

def recall_fact(key: str, category: str = "past") -> str:
    try:
        val = fetch_memory(key=key, category=category)
        if val is None:
            return f"No memory found for key '{key}' under category '{category}'."
        return str(val)
    except Exception as e:
        return f"Error fetching memory: {e}"

def forget_fact(key: str, category: str = "past") -> str:
    try:
        delete_memory(key=key, category=category)
        return f"Deleted memory '{key}' from category '{category}'."
    except Exception as e:
        return f"Error deleting memory: {e}"

def search_chat(query: str, limit: int = 5) -> str:
    try:
        from src.CoreFunctions.Infrastructure.vector_memory import search_vector
        matches = search_vector(query, limit=limit)
        if not matches:
            return "No matching conversations found."
        return str(matches)
    except Exception as e:
        return f"Error searching chat history: {e}"

def search_skills(query: str) -> str:
    try:
        matches = search_skills_vector(query, limit=3)
        return str(matches)
    except Exception as e:
        return f"Error searching skills: {e}"

def update_skill_content(skill_name: str, content: str) -> str:
    try:
        import os
        skill_path = os.path.join("Skills", skill_name, "SKILL.md")
        os.makedirs(os.path.dirname(skill_path), exist_ok=True)
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Skill '{skill_name}' updated successfully."
    except Exception as e:
        return f"Error updating skill: {e}"
