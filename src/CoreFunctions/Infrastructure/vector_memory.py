import os
import sys
import json
import time
from typing import List, Dict, Any

# Global placeholders for lazy-loaded dependencies
MODEL = None
DIM = 384

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
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
        
        local_model_path = os.path.join(BASE_DIR, "models", "embedding", "bge-small-en-v1.5")
        model_name_or_path = local_model_path if os.path.exists(local_model_path) else "BAAI/bge-small-en-v1.5"
        
        with open(os.devnull, "w") as f:
            with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
                from sentence_transformers import SentenceTransformer
                try:
                    MODEL = SentenceTransformer(
                        model_name_or_path, 
                        local_files_only=os.path.exists(local_model_path), 
                        device="cpu"
                    )
                except Exception:
                    MODEL = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
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

METADATA_PATH = os.path.join(BASE_DIR, "Memory", "vector_store", "metadata.json")
COLD_ARCHIVE_PATH = os.path.join(BASE_DIR, "Memory", "vector_store", "cold_archive.json")

def _load_metadata():
    if os.path.exists(METADATA_PATH):
        try:
            with open(METADATA_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_metadata(metadata):
    try:
        with open(METADATA_PATH, "w") as f:
            json.dump(metadata, f, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save metadata: {e}")

def _calculate_score(item_metadata: dict) -> float:
    ts = item_metadata.get("timestamp", time.time())
    access_count = item_metadata.get("access_count", 1)
    
    elapsed_seconds = time.time() - ts
    decay_factor = 0.95
    elapsed_days = elapsed_seconds / 86400.0
    
    return access_count * (decay_factor ** elapsed_days)

def store_vector(text, source="stated"):
    with _vector_lock:
        index = _load_index()
        data = _load_data()
        metadata = _load_metadata()
        
        # Ensure metadata matches data length
        if len(metadata) != len(data):
            metadata = [{"timestamp": time.time(), "access_count": 1, "source": "stated"} for _ in range(len(data))]
            _save_metadata(metadata)

        # Normalize the incoming text
        normalized_text = text.strip().lower()
        
        # 1. Exact string checking loop to prevent duplicated text entries
        for i, item in enumerate(data):
            if item.strip().lower() == normalized_text:
                print(f"ℹ️ [Vector Store] Fact already exists: \"{text}\". Updating access count and timestamp.")
                metadata[i]["access_count"] = metadata[i].get("access_count", 1) + 1
                metadata[i]["timestamp"] = time.time()
                _save_metadata(metadata)
                
                # Sync update to SQL
                try:
                    from .unified_memory import UnifiedMemory
                    um = UnifiedMemory()
                    um.engine.upsert_vector_fact(
                        item, 
                        source=metadata[i].get("source", source), 
                        timestamp=metadata[i]["timestamp"], 
                        access_count=metadata[i]["access_count"]
                    )
                except Exception as e:
                    pass
                return

        # 2. Semantic duplication check (if index has entries)
        if index.ntotal > 0:
            model = _get_model()
            q = model.encode([text])
            D, idx = index.search(q, 1)  # Find the single closest vector match
            if len(D) > 0 and len(D[0]) > 0:
                distance = D[0][0]
                if distance < 0.1:
                    matched_idx = idx[0][0]
                    matched_text = data[matched_idx]
                    print(f"ℹ️ [Vector Store] Highly similar fact already exists (distance={distance:.4f}):\n"
                          f"   New: \"{text}\"\n"
                          f"   Existing: \"{matched_text}\"\n"
                          f"   Updating access count and timestamp of existing fact.")
                    metadata[matched_idx]["access_count"] = metadata[matched_idx].get("access_count", 1) + 1
                    metadata[matched_idx]["timestamp"] = time.time()
                    _save_metadata(metadata)
                    
                    # Sync update to SQL
                    try:
                        from .unified_memory import UnifiedMemory
                        um = UnifiedMemory()
                        um.engine.upsert_vector_fact(
                            matched_text, 
                            source=metadata[matched_idx].get("source", source), 
                            timestamp=metadata[matched_idx]["timestamp"], 
                            access_count=metadata[matched_idx]["access_count"]
                        )
                    except Exception as e:
                        pass
                    return

        import numpy as np
        model = _get_model()
        vec = model.encode([text])
        index.add(np.array(vec, dtype=np.float32))
        data.append(text)
        metadata.append({"timestamp": time.time(), "access_count": 1, "source": source})

        # Sync insert to SQL
        try:
            from .unified_memory import UnifiedMemory
            um = UnifiedMemory()
            um.engine.upsert_vector_fact(text, source=source, timestamp=time.time(), access_count=1)
        except Exception as e:
            pass

        # Impose CAP of 50 facts (Problem 5)
        MAX_FACTS = 50
        if len(data) > MAX_FACTS:
            # Calculate scores for all facts
            scores = [_calculate_score(meta) for meta in metadata]
            lowest_idx = scores.index(min(scores))
            
            demoted_text = data[lowest_idx]
            demoted_meta = metadata[lowest_idx]
            print(f"📉 [Relevance-Decay] demoting fact with lowest score ({scores[lowest_idx]:.4f}) to cold store:\n"
                  f"   \"{demoted_text}\"")
            
            cold_archive = []
            if os.path.exists(COLD_ARCHIVE_PATH):
                try:
                    with open(COLD_ARCHIVE_PATH, "r") as f:
                        cold_archive = json.load(f)
                except Exception:
                    pass
            cold_archive.append({
                "text": demoted_text,
                "metadata": demoted_meta,
                "archived_at": time.time()
            })
            try:
                with open(COLD_ARCHIVE_PATH, "w") as f:
                    json.dump(cold_archive, f, indent=2)
            except Exception as e:
                print(f"⚠️ Failed to write cold archive: {e}")
                
            # Remove from SQLite
            try:
                from .unified_memory import UnifiedMemory
                um = UnifiedMemory()
                um.engine.delete_vector_fact(demoted_text)
            except Exception:
                pass
                
            data.pop(lowest_idx)
            metadata.pop(lowest_idx)
            
            # Rebuild index from remaining data
            import faiss
            index = faiss.IndexFlatL2(DIM)
            if data:
                vecs = model.encode(data)
                index.add(np.array(vecs, dtype=np.float32))
                
        _save(index, data)
        _save_metadata(metadata)

def search_vector(query, k=3, threshold=None):
    with _vector_lock:
        index = _load_index()
        data = _load_data()
        metadata = _load_metadata()
        
        # Ensure metadata matches data length
        if len(metadata) != len(data):
            metadata = [{"timestamp": time.time(), "access_count": 1} for _ in range(len(data))]
            _save_metadata(metadata)
            
        if index.ntotal == 0:
            return []

        import numpy as np
        model = _get_model()
        q = model.encode([query])
        D, idx = index.search(np.array(q, dtype=np.float32), min(k, index.ntotal))
        
        results = []
        updated = False
        for i, dist in zip(idx[0], D[0]):
            if i < len(data) and i != -1:
                if threshold is None or dist <= threshold:
                    results.append(data[i])
                    
                    # Update metadata on retrieval/access
                    metadata[i]["access_count"] = metadata[i].get("access_count", 0) + 1
                    metadata[i]["timestamp"] = time.time()
                    updated = True
                    
        if updated:
            _save_metadata(metadata)
            
        return results


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
    import hashlib
    
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
                        
                content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
                skills_list.append({
                    "name": name,
                    "description": description,
                    "category": category,
                    "tags": tags,
                    "path": skill_md_path,
                    "content_hash": content_hash
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
        
        # Self-healing check: check if any matched/listed skill references a file path that no longer exists or if hash differs
        stale_found = False
        import hashlib
        skills_dir = os.path.join(BASE_DIR, "Skills")
        existing_paths = []
        if os.path.exists(skills_dir):
            for root, _, files in os.walk(skills_dir):
                if "SKILL.md" in files:
                    existing_paths.append(os.path.join(root, "SKILL.md"))
        
        if len(existing_paths) != len(data):
            stale_found = True
        else:
            for skill in data:
                skill_path = skill.get("path")
                if not skill_path or not os.path.exists(skill_path):
                    stale_found = True
                    break
                try:
                    with open(skill_path, "r", encoding="utf-8") as sf:
                        current_content = sf.read()
                    current_hash = hashlib.md5(current_content.encode("utf-8")).hexdigest()
                    if current_hash != skill.get("content_hash"):
                        stale_found = True
                        break
                except Exception:
                    stale_found = True
                    break
                
        if stale_found:
            print("⚠️ Stale skills detected (some skill files are deleted/missing/modified). Rebuilding vector store...")
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
            
        # Remove from SQLite
        try:
            from .unified_memory import UnifiedMemory
            um = UnifiedMemory()
            # Find and delete exact matching fact from SQLite
            for f in um.engine.list_vector_facts():
                if f["fact"].strip().lower() == normalized_target:
                    um.engine.delete_vector_fact(f["fact"])
        except Exception as e:
            pass

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

def rebuild_general_vector_store():
    """Rebuilds the general FAISS index from the facts stored in SQLite vector_facts table."""
    import faiss
    import numpy as np
    
    try:
        from .unified_memory import UnifiedMemory
        um = UnifiedMemory()
        facts_db = um.engine.list_vector_facts()
    except Exception as e:
        print(f"⚠️ Error querying SQLite for general vector rebuild: {e}")
        facts_db = []
        
    if not facts_db:
        # Fallback to data.json if SQL has no facts, to be safe
        data = _load_data()
        metadata = _load_metadata()
        # Sync these back to SQL so SQL populates
        try:
            from .unified_memory import UnifiedMemory
            um = UnifiedMemory()
            for idx, fact in enumerate(data):
                meta = metadata[idx] if idx < len(metadata) else {}
                um.engine.upsert_vector_fact(
                    fact, 
                    source=meta.get("source", "stated"),
                    timestamp=meta.get("timestamp", time.time()),
                    access_count=meta.get("access_count", 1)
                )
        except Exception:
            pass
    else:
        # Reconstruct data.json and metadata.json from SQL
        data = [f["fact"] for f in facts_db]
        metadata = [{
            "timestamp": f["timestamp"], 
            "access_count": f["access_count"], 
            "source": f["source"]
        } for f in facts_db]
        
    if not data:
        index = faiss.IndexFlatL2(DIM)
        faiss.write_index(index, INDEX_PATH)
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
        _save_metadata([])
        return
        
    model = _get_model()
    embeddings = model.encode(data)
    index = faiss.IndexFlatL2(DIM)
    index.add(np.array(embeddings, dtype=np.float32))
    
    faiss.write_index(index, INDEX_PATH)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    _save_metadata(metadata)
    print(f"✅ Rebuilt General Vector Store with {len(data)} facts.")

VERSION_FILE_PATH = os.path.join(BASE_DIR, "Memory", "vector_store", "model_version.txt")
CURRENT_MODEL_NAME = "BAAI/bge-small-en-v1.5"

def check_and_migrate_embeddings():
    """Checks if the embedding model version matches BGE. If not, clears indices and rebuilds them."""
    needs_rebuild = False
    
    if os.path.exists(VERSION_FILE_PATH):
        try:
            with open(VERSION_FILE_PATH, "r", encoding="utf-8") as f:
                ver = f.read().strip()
            if ver != CURRENT_MODEL_NAME:
                needs_rebuild = True
        except Exception:
            needs_rebuild = True
    else:
        needs_rebuild = True
        
    if needs_rebuild:
        print(f"🔄 [Embeddings Upgrade] Swapping vector embedding model to '{CURRENT_MODEL_NAME}'...")
        print("🧹 Clearing legacy FAISS indices to prevent semantic coordinate mismatch...")
        
        for path in [INDEX_PATH, SKILLS_INDEX_PATH]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"  ⚠️ Warning: Could not delete legacy index file '{path}': {e}")
                    
        try:
            rebuild_general_vector_store()
            rebuild_skills_vector_store()
            with open(VERSION_FILE_PATH, "w", encoding="utf-8") as f:
                f.write(CURRENT_MODEL_NAME)
            print("🎉 [Embeddings Upgrade] Rebuilt all FAISS vector stores successfully.")
        except Exception as e:
            print(f"  ❌ Failed to rebuild FAISS vector stores: {e}")

# Run automatic migration validation on import
check_and_migrate_embeddings()


def consolidate_facts() -> None:
    """
    Scans the general facts vector store. If capacity exceeds 80% (40/50 facts),
    runs pairwise semantic similarity check and uses Gemini to merge near-duplicates.
    """
    with _vector_lock:
        data = _load_data()
        metadata = _load_metadata()
        index = _load_index()
        
        if len(data) < 40 or index.ntotal == 0:
            return
            
        print("🔄 [Memory Consolidation] Active facts count exceeds 80% capacity. Scanning for near-duplicates...")
        
        model = _get_model()
        merged_indices = set()
        to_add = []
        
        import numpy as np
        for i in range(len(data)):
            if i in merged_indices:
                continue
                
            fact1 = data[i]
            vec = model.encode([fact1])
            D, idx = index.search(np.array(vec, dtype=np.float32), 2)
            
            if len(D) > 0 and len(D[0]) > 1:
                other_idx = idx[0][1]
                distance = D[0][1]
                
                if other_idx != -1 and other_idx != i and other_idx not in merged_indices:
                    # Threshold for near-duplicates is distance < 0.35 in IndexFlatL2
                    if distance < 0.35:
                        fact2 = data[other_idx]
                        print(f"   ↳ Found near-duplicates (distance={distance:.4f}):\n"
                              f"     1: \"{fact1}\"\n"
                              f"     2: \"{fact2}\"\n"
                              f"     Consolidating using Gemini...")
                              
                        merged_indices.add(i)
                        merged_indices.add(other_idx)
                        
                        try:
                            from src.CoreFunctions.Infrastructure.llm_factory import get_llm
                            from langchain_core.messages import SystemMessage, HumanMessage
                            
                            model_name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
                            llm = get_llm(model_name, temperature=0)
                            
                            prompt = (
                                "You are a memory consolidation optimizer. Combine the following two semantically similar statements "
                                "into a single, cohesive, fact-based sentence. Do not lose any key information. Keep the output extremely "
                                "concise and under 150 characters.\n\n"
                                f"Statement 1: {fact1}\n"
                                f"Statement 2: {fact2}\n\n"
                                "Merged Statement:"
                            )
                            resp = llm.invoke([
                                SystemMessage(content="You are a precise backend memory consolidation engine."),
                                HumanMessage(content=prompt)
                            ])
                            merged_text = str(resp.content).strip().strip('"').strip("'")
                            print(f"     🎉 Result: \"{merged_text}\"")
                            to_add.append(merged_text)
                        except Exception as e:
                            print(f"     ⚠️ Consolidation failed: {e}. Keeping both statements.")
                            merged_indices.remove(i)
                            merged_indices.remove(other_idx)
                            
        if merged_indices:
            new_data = [data[i] for i in range(len(data)) if i not in merged_indices]
            new_metadata = [metadata[i] for i in range(len(metadata)) if i not in merged_indices]
            
            for item in to_add:
                new_data.append(item)
                new_metadata.append({"timestamp": time.time(), "access_count": 2})
                
            import faiss
            index = faiss.IndexFlatL2(DIM)
            if new_data:
                vecs = model.encode(new_data)
                index.add(np.array(vecs, dtype=np.float32))
                
            _save(index, new_data)
            _save_metadata(new_metadata)
            print(f"✨ [Memory Consolidation] Completed. Reduced active facts from {len(data)} to {len(new_data)}.")

