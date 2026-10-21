import os
import json
import re
from typing import Dict, Any, List, Optional

VAULT_DIR = os.getenv("OBSIDIAN_VAULT_PATH", "workspace/obsidian_vault")

def _get_vault_path(*parts: str) -> str:
    path = os.path.abspath(os.path.join(VAULT_DIR, *parts))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path

def create_note(filename: str, content: str, folder: str = "") -> str:
    if not filename.endswith(".md"):
        filename += ".md"
    file_path = _get_vault_path(folder, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Created note '{filename}' at {file_path}"

def append_note(filename: str, content: str, folder: str = "") -> str:
    if not filename.endswith(".md"):
        filename += ".md"
    file_path = _get_vault_path(folder, filename)
    mode = "a" if os.path.exists(file_path) else "w"
    with open(file_path, mode, encoding="utf-8") as f:
        f.write("\n" + content if mode == "a" else content)
    return f"Appended content to '{filename}'"

def search_vault(query: str, folder: str = "") -> List[Dict[str, Any]]:
    search_root = os.path.join(VAULT_DIR, folder) if folder else VAULT_DIR
    if not os.path.exists(search_root):
        return []
    results = []
    q_lower = query.lower()
    for root, _, files in os.walk(search_root):
        for file in files:
            if file.endswith((".md", ".canvas")):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, VAULT_DIR)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                    if q_lower in file.lower() or q_lower in text.lower():
                        results.append({
                            "file": rel_path,
                            "match": file if q_lower in file.lower() else "content match"
                        })
                except Exception:
                    pass
    return results

def get_backlinks(filename: str) -> List[str]:
    base_name = os.path.splitext(os.path.basename(filename))[0]
    link_pattern = re.compile(rf"\[\[{re.escape(base_name)}(\|.*?)?\]\]", re.IGNORECASE)
    backlinks = []
    if not os.path.exists(VAULT_DIR):
        return []
    for root, _, files in os.walk(VAULT_DIR):
        for f in files:
            if f.endswith(".md") and not f.startswith(base_name):
                p = os.path.join(root, f)
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as note_file:
                        if link_pattern.search(note_file.read()):
                            backlinks.append(os.path.relpath(p, VAULT_DIR))
                except Exception:
                    pass
    return backlinks

def get_properties(filename: str) -> Dict[str, Any]:
    if not filename.endswith(".md"):
        filename += ".md"
    file_path = _get_vault_path(filename)
    if not os.path.exists(file_path):
        return {"error": "Note not found"}
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    props = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            props[k.strip()] = v.strip()
    return props

def update_properties(filename: str, properties: Dict[str, Any]) -> str:
    if not filename.endswith(".md"):
        filename += ".md"
    file_path = _get_vault_path(filename)
    content = ""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    frontmatter_lines = ["---"]
    for k, v in properties.items():
        frontmatter_lines.append(f"{k}: {v}")
    frontmatter_lines.append("---")
    new_fm = "\n".join(frontmatter_lines)
    if re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL):
        content = re.sub(r"^---\s*\n(.*?)\n---", new_fm, content, flags=re.DOTALL)
    else:
        content = f"{new_fm}\n{content}"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Updated properties for '{filename}'"

def create_or_update_canvas(canvas_name: str, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], folder: str = "") -> str:
    if not canvas_name.endswith(".canvas"):
        canvas_name += ".canvas"
    file_path = _get_vault_path(folder, canvas_name)
    canvas_data = {"nodes": nodes, "edges": edges}
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(canvas_data, f, indent=2)
    return f"Canvas '{canvas_name}' created at {file_path}"
