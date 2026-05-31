import os
import sys
import json

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
_vector_lock = threading.Lock()

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
