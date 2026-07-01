import json
import os
from langchain_core.tools import StructuredTool

# Import all infra helpers that tools might need
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector, delete_vector_fact, rebuild_skills_vector_store, search_skills_vector
from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory


def search_skills_tool(query: str, count: int = 2) -> str:
    """Semantically searches for available system skills matching the query.
    This tool is read-only and does not require password verification.
    
    Args:
        query (str): The search query or goal description (e.g., 'send email via gmail', 'obsidian canvas coordinate grid').
        count (int, optional): The number of top matching skills to return. Defaults to 2.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: search_skills_tool")
    print(f"   Args: query='{query}', count={count}")
    
    try:
        from src.CoreFunctions.Infrastructure.vector_memory import search_skills_vector
        matched = search_skills_vector(query, k=count)
        if not matched:
            return "No matching skills found."
            
        results = []
        for skill in matched:
            skill_path = skill.get("path")
            if skill_path and os.path.exists(skill_path):
                try:
                    with open(skill_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    results.append(f"### Skill File: {skill_path}\n\n{content}")
                except Exception as read_ex:
                    results.append(f"### Skill: {skill.get('name')} (Error reading file: {read_ex})")
            else:
                results.append(f"### Skill: {skill.get('name')} (Description: {skill.get('description')}) - Path not found.")
                
        return "\n\n---\n\n".join(results)
    except Exception as e:
        return f"❌ Error searching skills: {e}"

memory_worker_tool_search_skills = StructuredTool.from_function(
    func=search_skills_tool,
    name="search_skills",
    description="Semantically searches for available system skills matching the query. This tool is read-only and does not require password verification."
)
