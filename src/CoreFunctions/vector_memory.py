import os
import sys
import json
from typing import List, Dict, Any

# Global placeholders for lazy-loaded dependencies
MODEL = None
DIM = 384

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INDEX_PATH = os.path.join(BASE_DIR, "Memory", "vector_store", "index.faiss")
DATA_PATH = os.path.join(BASE_DIR, "Memory", "vector_store", "data.json")

os.makedirs(os.path.join(BASE_DIR, "Memory", "vector_store"), exist_ok=True)

def _get_model():
    """Lazily loads the SentenceTransformer model on first call, keeping CLI startup instant."""
    global MODEL
    if MODEL is None:
        import warnings
        import logging
        import contextlib
        
        # Suppress warnings & logs
        warnings.filterwarnings("ignore")
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        logging.getLogger("transformers").setLevel(logging.ERROR)
        logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
        logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
        
        with open(os.devnull, "w") as f:
            with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
                from sentence_transformers import SentenceTransformer
                try:
                    # Attempt instant offline load first to prevent remote network checks and hangs
                    MODEL = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
                except Exception:
                    # Fallback to online download/check only if not cached locally
                    MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return MODEL

def _load_index():
    """Lazily loads FAISS library and reads the index file."""
    import faiss
    if os.path.exists(INDEX_PATH):
        return faiss.read_index(INDEX_PATH)
    return faiss.IndexFlatL2(DIM)

def _load_data():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r") as f:
            return json.load(f)
    return []

def _save(index, data):
    import faiss
    faiss.write_index(index, INDEX_PATH)
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)

import threading

# Thread lock to prevent race conditions during concurrent FAISS/JSON vector accesses
_vector_lock = threading.RLock()

def store_vector(text):
    with _vector_lock:
        index = _load_index()
        data = _load_data()

        # Normalize the incoming text
        normalized_text = text.strip().lower()
        
        # 1. Exact string checking loop to prevent duplicated text entries
        for item in data:
            if item.strip().lower() == normalized_text:
                print(f"ℹ️ [Vector Store] Fact already exists: \"{text}\". Skipping store to avoid duplication.")
                return

        # 2. Semantic duplication check (if index has entries)
        if index.ntotal > 0:
            model = _get_model()
            q = model.encode([text])
            D, idx = index.search(q, 1)  # Find the single closest vector match
            if len(D) > 0 and len(D[0]) > 0:
                distance = D[0][0]
                # In FAISS IndexFlatL2, a distance < 0.1 represents almost identical embedding semantic meaning
                if distance < 0.1:
                    matched_text = data[idx[0][0]]
                    print(f"ℹ️ [Vector Store] Highly similar fact already exists (distance={distance:.4f}):\n"
                          f"   New: \"{text}\"\n"
                          f"   Existing: \"{matched_text}\"\n"
                          f"   Skipping store to avoid duplication.")
                    return

            model = _get_model()
            vec = model.encode([text])
            index.add(vec)
            data.append(text)

            _save(index, data)

def search_vector(query, k=3):
    with _vector_lock:
        index = _load_index()
        data = _load_data()
        if index.ntotal == 0:
            return []

        model = _get_model()
        q = model.encode([query])
        _, idx = index.search(q, k)
        return [data[i] for i in idx[0] if i < len(data)]

# --- Dedicated Skills Vector Store ---

SKILLS_INDEX_PATH = os.path.join(BASE_DIR, "Memory", "vector_store", "skills_index.faiss")
SKILLS_DATA_PATH = os.path.join(BASE_DIR, "Memory", "vector_store", "skills_data.json")

def _load_skills_index():
    import faiss
    if os.path.exists(SKILLS_INDEX_PATH):
        return faiss.read_index(SKILLS_INDEX_PATH)
    return faiss.IndexFlatL2(DIM)

def _load_skills_data() -> List[Dict[str, Any]]:
    if os.path.exists(SKILLS_DATA_PATH):
        with open(SKILLS_DATA_PATH, "r") as f:
            return json.load(f)
    return []

def rebuild_skills_vector_store():
    """Scans the Skills/ directory, reads SKILL.md files, builds FAISS index, and saves to skills_index.faiss."""
    import re
    import faiss
    import numpy as np
    
    skills_dir = os.path.join(BASE_DIR, "Skills")
    if not os.path.exists(skills_dir) or not os.path.isdir(skills_dir):
        return
        
    skills_list = []
    
    for root, dirs, files in os.walk(skills_dir):
        if "SKILL.md" in files:
            skill_md_path = os.path.join(root, "SKILL.md")
            try:
                with open(skill_md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Parse YAML frontmatter
                meta_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                name = os.path.basename(root)
                description = ""
                category = "general"
                tags = []
                
                if meta_match:
                    meta_text = meta_match.group(1)
                    name_match = re.search(r'name:\s*(.*)', meta_text)
                    if name_match:
                        name = name_match.group(1).strip()
                    desc_match = re.search(r'description:\s*(.*)', meta_text)
                    if desc_match:
                        description = desc_match.group(1).strip().strip('"').strip("'")
                    cat_match = re.search(r'category:\s*(.*)', meta_text)
                    if cat_match:
                        category = cat_match.group(1).strip()
                    tags_match = re.search(r'tags:\s*\[(.*?)\]', meta_text)
                    if tags_match:
                        tags = [t.strip().strip('"').strip("'") for t in tags_match.group(1).split(",") if t.strip()]
                        
                skills_list.append({
                    "name": name,
                    "description": description,
                    "category": category,
                    "tags": tags,
                    "path": skill_md_path
                })
            except Exception as e:
                print(f"  ⚠️ Error loading skill metadata for indexing: {e}")

    if not skills_list:
        with _vector_lock:
            index = faiss.IndexFlatL2(DIM)
            faiss.write_index(index, SKILLS_INDEX_PATH)
            with open(SKILLS_DATA_PATH, "w") as f:
                json.dump([], f)
        return

    # Create texts to embed
    texts_to_embed = []
    for s in skills_list:
        text = f"Skill: {s['name']} | Description: {s['description']} | Tags: {', '.join(s['tags'])}"
        texts_to_embed.append(text)

    # Encode embeddings
    model = _get_model()
    embeddings = model.encode(texts_to_embed)

    # Save index
    with _vector_lock:
        index = faiss.IndexFlatL2(DIM)
        index.add(np.array(embeddings, dtype=np.float32))
        faiss.write_index(index, SKILLS_INDEX_PATH)
        with open(SKILLS_DATA_PATH, "w") as f:
            json.dump(skills_list, f, indent=2)
            
    print(f"✅ Rebuilt Skills Vector Store with {len(skills_list)} skills.")


def search_skills_vector(query: str, k: int = 2) -> List[Dict[str, Any]]:
    """Semantically searches for skills matching the query using FAISS vector store."""
    # Ensure database is built at least once
    if not os.path.exists(SKILLS_INDEX_PATH) or not os.path.exists(SKILLS_DATA_PATH):
        print("📁 Skills Vector Store missing. Indexing skills first...")
        rebuild_skills_vector_store()
        
    with _vector_lock:
        index = _load_skills_index()
        data = _load_skills_data()
        
        # Self-healing check: check if any matched/listed skill references a file path that no longer exists
        stale_found = False
        for skill in data:
            skill_path = skill.get("path")
            if not skill_path or not os.path.exists(skill_path):
                stale_found = True
                break
                
        if stale_found:
            print("⚠️ Stale skills detected (some skill files are deleted/missing). Rebuilding vector store...")
            rebuild_skills_vector_store()
            index = _load_skills_index()
            data = _load_skills_data()

        if index.ntotal == 0 or not data:
            return []

        model = _get_model()
        q = model.encode([query])
        _, idx = index.search(q, k)
        
        results = []
        for i in idx[0]:
            if i < len(data):
                # Extra safety: verify that the matched skill path exists before returning
                skill_path = data[i].get("path")
                if skill_path and os.path.exists(skill_path):
                    results.append(data[i])
        return results


def delete_vector_fact(text: str) -> bool:
    """Removes a specific fact from the vector database and rebuilds the FAISS index."""
    import faiss
    import numpy as np
    with _vector_lock:
        data = _load_data()
        normalized_target = text.strip().lower()
        
        # Find and remove matching facts (case-insensitive comparison)
        new_data = [item for item in data if item.strip().lower() != normalized_target]
        
        if len(new_data) == len(data):
            return False
            
        # Re-build index from scratch with the remaining facts
        if len(new_data) > 0:
            model = _get_model()
            embeddings = model.encode(new_data)
            index = faiss.IndexFlatL2(DIM)
            index.add(np.array(embeddings, dtype=np.float32))
            faiss.write_index(index, INDEX_PATH)
        else:
            index = faiss.IndexFlatL2(DIM)
            faiss.write_index(index, INDEX_PATH)
            
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2)
            
        print(f"🗑️ [Vector Store] Removed fact: \"{text}\"")
        return True

