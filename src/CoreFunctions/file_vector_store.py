import os
import sys
import json
import threading
from CoreFunctions.security_utils import is_path_safe

# Global placeholders for lazy loading
MODEL = None
DIM = 384

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES_INDEX_PATH = os.path.join(BASE_DIR, "Memory", "vector_store", "files_index.faiss")
FILES_DATA_PATH = os.path.join(BASE_DIR, "Memory", "vector_store", "files_data.json")

os.makedirs(os.path.join(BASE_DIR, "Memory", "vector_store"), exist_ok=True)

# Thread lock to prevent race conditions during concurrent accesses
_file_vector_lock = threading.Lock()

def _get_model():
    """Lazily loads the SentenceTransformer model on first call."""
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
                    MODEL = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
                except Exception:
                    MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return MODEL

def _load_index():
    """Lazily loads FAISS library and reads the index file."""
    import faiss
    if os.path.exists(FILES_INDEX_PATH):
        return faiss.read_index(FILES_INDEX_PATH)
    return faiss.IndexFlatL2(DIM)

def _load_data():
    if os.path.exists(FILES_DATA_PATH):
        with open(FILES_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def _save(index, data):
    import faiss
    faiss.write_index(index, FILES_INDEX_PATH)
    with open(FILES_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def chunk_text_by_lines(text, max_chars=800, overlap_lines=2):
    """
    Chunks text into character limits while tracking exact starting and ending line numbers.
    """
    lines = text.split("\n")
    chunks = []
    current_lines = []
    current_char_count = 0
    start_line = 1
    
    for i, line in enumerate(lines):
        line_num = i + 1
        current_lines.append(line)
        current_char_count += len(line) + 1
        
        if current_char_count >= max_chars:
            chunks.append({
                "text": "\n".join(current_lines),
                "start_line": start_line,
                "end_line": line_num
            })
            # Handle overlap
            overlap = min(overlap_lines, len(current_lines))
            if overlap > 0:
                current_lines = current_lines[-overlap:]
                start_line = line_num - overlap + 1
                current_char_count = sum(len(l) + 1 for l in current_lines)
            else:
                current_lines = []
                start_line = line_num + 1
                current_char_count = 0
                
    if current_lines:
        chunks.append({
            "text": "\n".join(current_lines),
            "start_line": start_line,
            "end_line": len(lines)
        })
    return chunks

def index_file(filepath):
    """
    Reads, chunks, and indexes a single text file into the FAISS store.
    Removes existing chunks for the same file to allow clean updates.
    """
    abs_path = os.path.abspath(filepath)
    if not is_path_safe(abs_path):
        return f"❌ Security Violation: Path '{filepath}' is outside sandbox."
        
    if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
        return f"❌ Error: File '{filepath}' does not exist or is not a file."

    # Skip files that are likely binary or extremely large
    if os.path.getsize(abs_path) > 3 * 1024 * 1024: # 3MB Limit
        return f"ℹ️ Skipping '{filepath}': File exceeds 3MB limit."

    try:
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        return f"❌ Error reading file '{filepath}': {e}"

    chunks = chunk_text_by_lines(content)
    if not chunks:
        return f"ℹ️ File '{filepath}' is empty. Nothing to index."

    with _file_vector_lock:
        index = _load_index()
        data = _load_data()
        
        # Remove any existing chunks for this file to prevent duplicates on update
        import numpy as np
        import faiss
        
        filtered_data = []
        keep_indices = []
        for i, item in enumerate(data):
            if item.get("filepath") != abs_path:
                filtered_data.append(item)
                keep_indices.append(i)
        
        # Rebuild FAISS index with remaining vectors if some were deleted
        if len(keep_indices) != len(data):
            new_index = faiss.IndexFlatL2(DIM)
            if keep_indices and index.ntotal > 0:
                # Extract vectors to keep
                # IndexFlatL2 allows reconstructing vectors
                vectors = []
                for idx in keep_indices:
                    vectors.append(index.reconstruct(idx))
                new_index.add(np.array(vectors, dtype=np.float32))
            index = new_index
            data = filtered_data

        # Add new chunks to index
        model = _get_model()
        texts_to_embed = [c["text"] for c in chunks]
        embeddings = model.encode(texts_to_embed)
        
        index.add(np.array(embeddings, dtype=np.float32))
        
        for c, text in zip(chunks, texts_to_embed):
            data.append({
                "text": text,
                "filepath": abs_path,
                "start_line": c["start_line"],
                "end_line": c["end_line"]
            })
            
        _save(index, data)
        
    return f"✅ Successfully indexed '{os.path.basename(abs_path)}' ({len(chunks)} chunks)."

def index_directory_recursive(dir_path):
    """
    Recursively scans and indexes safe file types inside a sandboxed folder.
    Skips build, version control, and virtual environments.
    """
    abs_dir = os.path.abspath(dir_path)
    if not is_path_safe(abs_dir):
        return f"❌ Security Violation: Directory '{dir_path}' is outside sandbox."

    indexed_count = 0
    skipped_count = 0
    errors = []

    # Directories to completely ignore
    ignored_dirs = {".git", ".venv", "__pycache__", "node_modules", ".gemini", "build", "dist"}
    # File extensions to index
    allowed_exts = {".py", ".md", ".json", ".txt", ".csv", ".yaml", ".yml", ".ini", ".conf", ".sh", ".js", ".ts", ".html", ".css"}

    for root, dirs, files in os.walk(abs_dir):
        # Prune ignored directories in place
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        
        for file in files:
            _, ext = os.path.splitext(file)
            if ext.lower() in allowed_exts:
                file_path = os.path.join(root, file)
                res = index_file(file_path)
                if "Successfully" in res:
                    indexed_count += 1
                elif "Skipping" in res:
                    skipped_count += 1
                else:
                    errors.append(res)
                    
    summary = f"📁 Directory Indexing Complete for '{abs_dir}':\n" \
              f"  - Indexed files: {indexed_count}\n" \
              f"  - Skipped files: {skipped_count}\n"
    if errors:
        summary += f"  - Errors encountered: {len(errors)}\n(First 3 errors: {errors[:3]})"
    return summary

def search_files_semantically(query, k=5):
    """
    Queries the files index for chunks relevant to the query.
    """
    with _file_vector_lock:
        index = _load_index()
        data = _load_data()
        
        if index.ntotal == 0:
            return "ℹ️ Files index is empty. Please run 'index_folder' first."
            
        model = _get_model()
        q_vec = model.encode([query])
        
        D, idx = index.search(q_vec, k)
        
        results = []
        for dist, i in zip(D[0], idx[0]):
            if i < len(data) and i >= 0:
                item = data[i]
                rel_path = os.path.relpath(item["filepath"], BASE_DIR)
                results.append(
                    f"📄 File: {rel_path} (Lines {item['start_line']}-{item['end_line']}) | Distance: {dist:.4f}\n"
                    f"```\n{item['text']}\n```"
                )
                
        if not results:
            return "No matching chunks found in the index."
        return "\n\n".join(results)

def rag_qa_file(query, filepath):
    """
    Extracts relevant chunks specifically from a target file and answers the query using local RAG.
    """
    abs_path = os.path.abspath(filepath)
    if not is_path_safe(abs_path):
        return f"❌ Security Violation: Path '{filepath}' is outside sandbox."
        
    if not os.path.exists(abs_path):
        return f"❌ File not found at '{filepath}'."

    try:
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        return f"❌ Error reading file: {e}"

    chunks = chunk_text_by_lines(content, max_chars=600)
    if not chunks:
        return f"File '{filepath}' is empty."

    # Embed chunks of this specific file in-memory
    model = _get_model()
    chunk_texts = [c["text"] for c in chunks]
    embeddings = model.encode(chunk_texts)
    
    import faiss
    import numpy as np
    file_index = faiss.IndexFlatL2(DIM)
    file_index.add(np.array(embeddings, dtype=np.float32))
    
    # Search the query in this file
    q_vec = model.encode([query])
    D, idx = file_index.search(q_vec, min(3, len(chunks)))
    
    context_chunks = []
    for i in idx[0]:
        if i < len(chunks):
            c = chunks[i]
            context_chunks.append(f"[Lines {c['start_line']}-{c['end_line']}]:\n{c['text']}")
            
    context = "\n\n---\n\n".join(context_chunks)
    
    # Run the query through our LLM
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage
        
        # Load API keys from root .env or config/.env fallback
        root_env_path = os.path.join(BASE_DIR, ".env")
        config_env_path = root_env_path if os.path.exists(root_env_path) else os.path.join(BASE_DIR, "config", ".env")
        from dotenv import load_dotenv
        load_dotenv(config_env_path)
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite", 
            temperature=0
        )
        
        prompt = f"""You are a code/document analysis assistant.
You are helping answer a question about the file: '{os.path.basename(abs_path)}'.
Use ONLY the following matching chunks extracted from the file to answer the question.

Extracts from file '{os.path.basename(abs_path)}':
{context}

Question: {query}

Provide a concise, direct, and fact-based answer using the context extracts. If the context does not contain the answer, say that you cannot find it in the extracts. Do not make up information.
"""
        res = llm.invoke([HumanMessage(content=prompt)])
        return f"📝 **Answer for '{os.path.basename(abs_path)}':**\n{res.content}"
    except Exception as e:
        return f"❌ Error executing RAG QA: {e}\n\nMatching Context:\n{context}"
