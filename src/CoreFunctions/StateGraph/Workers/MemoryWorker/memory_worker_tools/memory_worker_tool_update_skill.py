import json
import os
from typing import List
from langchain_core.tools import StructuredTool

# Import all infra helpers that tools might need
from src.CoreFunctions.Infrastructure.memory import store_memory, fetch_memory, delete_memory
from src.CoreFunctions.Infrastructure.vector_memory import store_vector, search_vector, delete_vector_fact, rebuild_skills_vector_store, search_skills_vector
from src.CoreFunctions.Infrastructure.unified_memory import UnifiedMemory
from src.CoreFunctions.Infrastructure.auth_utils import verify_password

def _get_current_worker_name() -> str:
    """Helper to detect the name of the active worker node calling this tool from inspect stack."""
    import inspect
    for frame_info in inspect.stack():
        if frame_info.function in ["_run_ephemeral_agent", "_run_async_ephemeral_agent"]:
            worker_name = frame_info.frame.f_locals.get("worker_name")
            if worker_name:
                return worker_name
    return "general"


def update_skill_tool(
    skill_name: str,
    description: str = None,
    category: str = None,
    tags: List[str] = None,
    procedure: str = None,
    script_code: str = None,
    script_filename: str = None
) -> str:
    """Updates or creates a system skill's metadata, procedure, and/or automation script code. PROTECTED.
    
    Args:
        skill_name (str): The name of the skill (e.g., 'worker-status-ping').
        description (str, optional): A new description for the skill.
        category (str, optional): A new category (folder) for the skill. If different, the skill will be relocated.
        tags (list, optional): A list of tags/keywords for query matching.
        procedure (str, optional): Updated step-by-step markdown instructions for the skill.
        script_code (str, optional): Updated Python/Bash script content for automation.
        script_filename (str, optional): Filename for the automation script (e.g. 'check_status.py').
    """
    import re
    import shutil
    print(f"\n[DEBUG] 🛠️ Calling Tool: update_skill_tool")
    print(f"   Args: skill_name={skill_name}, category={category}")
    
    if not verify_password():
        return "❌ Action Cancelled: Incorrect Password."
        
    try:
        curr = os.path.abspath(__file__)
        while curr and not os.path.exists(os.path.join(curr, "src")):
            parent = os.path.dirname(curr)
            if parent == curr:
                curr = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
                break
            curr = parent
        base_dir = curr
        skills_dir = os.path.join(base_dir, "Skills")
        
        target_skill_md = None
        current_category = None
        
        if os.path.exists(skills_dir) and os.path.isdir(skills_dir):
            for root, dirs, files in os.walk(skills_dir):
                if "SKILL.md" in files:
                    skill_file = os.path.join(root, "SKILL.md")
                    folder_name = os.path.basename(root)
                    if folder_name.lower() == skill_name.lower():
                        target_skill_md = skill_file
                        rel_path = os.path.relpath(root, skills_dir)
                        parts = rel_path.split(os.sep)
                        if len(parts) > 1:
                            current_category = parts[0]
                        break
                    
                    try:
                        with open(skill_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        meta_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                        if meta_match:
                            name_match = re.search(r'name:\s*(.*)', meta_match.group(1))
                            if name_match and name_match.group(1).strip().lower() == skill_name.lower():
                                target_skill_md = skill_file
                                rel_path = os.path.relpath(root, skills_dir)
                                parts = rel_path.split(os.sep)
                                if len(parts) > 1:
                                    current_category = parts[0]
                                break
                    except Exception:
                        pass
                        
        is_new_skill = False
        if not target_skill_md:
            is_new_skill = True
            caller_worker = _get_current_worker_name()
            new_cat = category if category is not None else caller_worker
            new_cat_clean = re.sub(r'[^a-zA-Z0-9_-]', '-', new_cat.strip().lower())
            if not new_cat_clean:
                new_cat_clean = "general"
                
            existing_name = skill_name
            new_desc = description if description is not None else f"Custom skill for {skill_name}."
            new_category = new_cat
            new_tags = tags if tags is not None else [skill_name]
            
            if procedure is not None:
                if procedure.strip().startswith("#"):
                    new_procedure = procedure.strip()
                else:
                    new_procedure = f"""# {existing_name.replace("-", " ").title()}
                
## When to Use
Use this skill when you need to execute workflows related to {", ".join(new_tags)}.

## Procedure
{procedure.strip()}"""
            else:
                new_procedure = f"""# {existing_name.replace("-", " ").title()}
                
## When to Use
Use this skill when you need to execute workflows related to {", ".join(new_tags)}.

## Procedure
(No procedure specified yet)"""
            
            new_skill_folder = os.path.join(skills_dir, new_cat_clean, existing_name)
            current_skill_folder = new_skill_folder
            target_skill_md = os.path.join(new_skill_folder, "SKILL.md")
        else:
            with open(target_skill_md, "r", encoding="utf-8") as f:
                content = f.read()
            
            meta_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
            meta_text = meta_match.group(1) if meta_match else ""
            
            existing_name = skill_name
            existing_desc = ""
            existing_version = "1.0.0"
            existing_platforms = "[linux]"
            existing_category = current_category or "general"
            existing_tags = []
            
            if meta_text:
                name_m = re.search(r'name:\s*(.*)', meta_text)
                if name_m: existing_name = name_m.group(1).strip()
                
                desc_m = re.search(r'description:\s*(.*)', meta_text)
                if desc_m: existing_desc = desc_m.group(1).strip().strip('"').strip("'")
                
                ver_m = re.search(r'version:\s*(.*)', meta_text)
                if ver_m: existing_version = ver_m.group(1).strip()
                
                plat_m = re.search(r'platforms:\s*(.*)', meta_text)
                if plat_m: existing_platforms = plat_m.group(1).strip()
                
                cat_m = re.search(r'category:\s*(.*)', meta_text)
                if cat_m: existing_category = cat_m.group(1).strip()
                
                tags_m = re.search(r'tags:\s*\[(.*?)\]', meta_text)
                if tags_m:
                    existing_tags = [t.strip().strip('"').strip("'") for t in tags_m.group(1).split(",") if t.strip()]
                    
            existing_procedure = ""
            if meta_match:
                existing_procedure = content[meta_match.end():].strip()
                
            new_desc = description if description is not None else existing_desc
            new_category = category if category is not None else existing_category
            new_tags = tags if tags is not None else existing_tags
            
            new_category_clean = re.sub(r'[^a-zA-Z0-9_-]', '-', new_category.strip().lower())
            if not new_category_clean:
                new_category_clean = "general"
                
            if procedure is not None:
                if procedure.strip().startswith("#"):
                    new_procedure = procedure.strip()
                else:
                    new_procedure = f"""# {existing_name.replace("-", " ").title()}
                    
## When to Use
Use this skill when you need to execute workflows related to {", ".join(new_tags)}.
    
## Procedure
{procedure.strip()}"""
            else:
                new_procedure = existing_procedure
                
            current_skill_folder = os.path.dirname(target_skill_md)
            new_skill_folder = os.path.join(skills_dir, new_category_clean, existing_name)
            
            if new_skill_folder != current_skill_folder:
                os.makedirs(os.path.dirname(new_skill_folder), exist_ok=True)
                shutil.move(current_skill_folder, new_skill_folder)
                target_skill_md = os.path.join(new_skill_folder, "SKILL.md")
                current_skill_folder = new_skill_folder
                
        # Build new metadata block
        tags_str = ", ".join([f'"{t}"' for t in new_tags])
        new_skill_markdown = f"""---
name: {existing_name}
description: "{new_desc}"
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: {new_category}
    tags: [{tags_str}]
---
{new_procedure}"""

        os.makedirs(current_skill_folder, exist_ok=True)
        with open(target_skill_md, "w", encoding="utf-8") as f:
            f.write(new_skill_markdown.strip())
            
        result_msg = f"Successfully updated skill '{existing_name}' metadata at: {target_skill_md}"
        
        if script_code is not None and script_filename is not None:
            scripts_folder = os.path.join(current_skill_folder, "scripts")
            os.makedirs(scripts_folder, exist_ok=True)
            script_path = os.path.join(scripts_folder, script_filename)
            with open(script_path, "w", encoding="utf-8") as f_script:
                f_script.write(script_code.strip())
            result_msg += f"\nAnd saved/updated automation script at: {script_path}"
            
        # Trigger rebuild of skills vector store
        try:
            from src.CoreFunctions.Infrastructure.vector_memory import rebuild_skills_vector_store
            rebuild_skills_vector_store()
        except Exception as rebuild_ex:
            print(f"  ⚠️ Warning: Failed to rebuild skills vector store: {rebuild_ex}")

        return result_msg
    except Exception as e:
        return f"❌ Error updating skill: {e}"

memory_worker_tool_update_skill = StructuredTool.from_function(
    func=update_skill_tool,
    name="update_skill",
    description="Creates a new procedural skill or updates/deletes an existing system skill. Requires password verification."
)
