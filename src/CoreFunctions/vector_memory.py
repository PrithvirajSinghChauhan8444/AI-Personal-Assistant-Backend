from sentence_transformers import SentenceTransformer
import faiss
import os
import json

MODEL = SentenceTransformer("all-MiniLM-L6-v2")
DIM = 384

INDEX_PATH = "memory/vector_store/index.faiss"
DATA_PATH = "memory/vector_store/data.json"

os.makedirs("memory/vector_store", exist_ok=True)

def _load_index():
    if os.path.exists(INDEX_PATH):
        return faiss.read_index(INDEX_PATH)
    return faiss.IndexFlatL2(DIM)

def _load_data():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r") as f:
            return json.load(f)
    return []

def _save(index, data):
    faiss.write_index(index, INDEX_PATH)
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)

def store_vector(text):
    index = _load_index()
    data = _load_data()

    vec = MODEL.encode([text])
    index.add(vec)
    data.append(text)

    _save(index, data)

def search_vector(query, k=3):
    index = _load_index()
    data = _load_data()
    if index.ntotal == 0:
        return []

    q = MODEL.encode([query])
    _, idx = index.search(q, k)
    return [data[i] for i in idx[0] if i < len(data)]
