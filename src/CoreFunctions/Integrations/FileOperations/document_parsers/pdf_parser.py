"""
PDF Document Parser Module.
Includes PyMuPDF page layout classification, vector diagram scoring, image extraction, MD5 hash deduplication, document idempotency, and Gemini Vision captioning.
"""

import os
import json
import base64
import hashlib
from typing import List, Dict, Any, Tuple

CAPTION_HASH_CACHE: Dict[str, str] = {}

def get_file_md5(filepath: str) -> str:
    """Computes MD5 hash of a file for document idempotency."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_bytes_md5(raw_bytes: bytes) -> str:
    """Computes MD5 hash of raw bytes for image deduplication."""
    return hashlib.md5(raw_bytes).hexdigest()

def union_bbox(bboxes: List[Tuple[float, float, float, float]]) -> Tuple[float, float, float, float]:
    """Calculates the bounding box union of multiple bboxes [x0, y0, x1, y1]."""
    x0 = min(b[0] for b in bboxes)
    y0 = min(b[1] for b in bboxes)
    x1 = max(b[2] for b in bboxes)
    y1 = max(b[3] for b in bboxes)
    return (x0, y0, x1, y1)

def is_overlapping(rect1: Tuple[float, float, float, float], rect2: Tuple[float, float, float, float]) -> bool:
    """Checks if two bboxes overlap."""
    r1_x0, r1_y0, r1_x1, r1_y1 = rect1
    r2_x0, r2_y0, r2_x1, r2_y1 = rect2
    return not (r1_x1 < r2_x0 or r1_x0 > r2_x1 or r1_y1 < r2_y0 or r1_y0 > r2_y1)

def is_inside_box(inner_bbox: Tuple[float, float, float, float], outer_bbox: Tuple[float, float, float, float], margin: float = 5.0) -> bool:
    """Checks if inner_bbox is contained inside outer_bbox (with margin tolerance)."""
    ix0, iy0, ix1, iy1 = inner_bbox
    ox0, oy0, ox1, oy1 = outer_bbox
    return (ix0 >= ox0 - margin and iy0 >= oy0 - margin and ix1 <= ox1 + margin and iy1 <= oy1 + margin)

def is_valid_image(base_image: Dict[str, Any], min_dim: int = 100, min_size_bytes: int = 4096) -> bool:
    """Filters out tiny junk images (logos, bullets, thin decorative borders)."""
    image_bytes = base_image.get("image", b"")
    if len(image_bytes) < min_size_bytes:
        return False
        
    width = base_image.get("width", 0)
    height = base_image.get("height", 0)
    
    if width > 0 and height > 0:
        if width < min_dim or height < min_dim:
            return False
            
    return True

def score_cluster(cluster_blocks: List[Dict], drawings: List[Dict]) -> int:
    """Scores a cluster of text blocks to determine if it forms a diagram/flowchart."""
    score = 0
    if not cluster_blocks:
        return 0
    
    cluster_bbox = union_bbox([b["bbox"] for b in cluster_blocks])
    overlapping_drawings = sum(1 for d in drawings if is_overlapping(cluster_bbox, d["rect"]))
    if overlapping_drawings > 2:
        score += 2
    elif overlapping_drawings > 0:
        score += 1

    words_per_block = []
    for b in cluster_blocks:
        block_text = "".join(span["text"] for line in b.get("lines", []) for span in line.get("spans", []))
        words_per_block.append(len(block_text.split()))
    
    if words_per_block and sum(words_per_block) / len(words_per_block) < 7:
        score += 1
        
    return score

def is_whole_page_diagram(page, text_blocks: List[Dict], drawings: List[Dict]) -> bool:
    """Detects if an entire page is a slide, mind map, or full-page diagram."""
    rect = page.rect
    is_landscape = (rect.width > rect.height)
    has_heavy_drawings = (len(drawings) > 5)
    is_low_text_density = (len(text_blocks) < 15)
    
    return (is_landscape and has_heavy_drawings) or (is_low_text_density and has_heavy_drawings)

def classify_pdf_page(doc, page) -> Tuple[List[Tuple[float, float, float, float]], List[Any]]:
    """Classifies page components into vector diagram regions and valid embedded image xrefs."""
    try:
        from sklearn.cluster import DBSCAN
        has_dbscan = True
    except ImportError:
        has_dbscan = False

    text_page = page.get_text("dict")
    text_blocks = [b for b in text_page.get("blocks", []) if b.get("type") == 0]
    drawings = page.get_drawings()
    raw_images = page.get_images(full=True)

    valid_embedded_images = []
    for img_info in raw_images:
        xref = img_info[0]
        base_img = doc.extract_image(xref)
        if is_valid_image(base_img):
            valid_embedded_images.append(img_info)

    if is_whole_page_diagram(page, text_blocks, drawings):
        return [(0.0, 0.0, float(page.rect.width), float(page.rect.height))], valid_embedded_images

    diagram_regions = []
    if text_blocks and has_dbscan:
        import numpy as np
        centers = np.array([[(b["bbox"][0] + b["bbox"][2]) / 2.0, (b["bbox"][1] + b["bbox"][3]) / 2.0] for b in text_blocks])
        if len(centers) > 0:
            clusters = DBSCAN(eps=80, min_samples=1).fit(centers).labels_
            for label in set(clusters):
                if label == -1:
                    continue
                cluster_blocks = [text_blocks[i] for i in range(len(text_blocks)) if clusters[i] == label]
                score = score_cluster(cluster_blocks, drawings)
                if score >= 2:
                    diagram_regions.append(union_bbox([b["bbox"] for b in cluster_blocks]))

    return diagram_regions, valid_embedded_images

def load_environment():
    """Locates and loads .env from project root, config/.env, or current working directory."""
    try:
        from dotenv import load_dotenv
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
        
        candidates = [
            os.path.join(project_root, "config", ".env"),
            os.path.join(project_root, ".env"),
            os.path.join(os.getcwd(), "config", ".env"),
            os.path.join(os.getcwd(), ".env")
        ]
        for env_path in candidates:
            if os.path.exists(env_path):
                load_dotenv(env_path, override=True)
                break
    except Exception:
        pass

def caption_image_gemini(image_path: str, img_hash: str, kind: str = "diagram") -> str:
    """Captions image with Gemini Vision LLM using MD5 deduplication."""
    if img_hash in CAPTION_HASH_CACHE:
        return f"💡 **AI Caption ({kind} - Deduplicated)**: {CAPTION_HASH_CACHE[img_hash]}"

    load_environment()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        fallback_msg = f"[Caption skipped: API Key missing in env for {os.path.basename(image_path)}]"
        CAPTION_HASH_CACHE[img_hash] = fallback_msg
        return fallback_msg

    try:
        from src.CoreFunctions.Infrastructure.llm_factory import get_llm
        from langchain_core.messages import HumanMessage
        
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        ext = image_path.split(".")[-1].lower()
        mime_type = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
        
        prompt = (
            "Describe what this diagram or flowchart shows in detail. Mention all labeled boxes, arrows, text headers, and how components connect."
            if kind == "diagram" else
            "Describe what this image shows in detail to help answer future questions about it."
        )

        model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        llm = get_llm(model_name, temperature=0.1)
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{base64.b64encode(img_bytes).decode()}"}
                }
            ]
        )
        res = llm.invoke([message])
        if isinstance(res.content, list):
            text_parts = []
            for part in res.content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
                elif hasattr(part, "text"):
                    text_parts.append(str(part.text))
            caption = "".join(text_parts).strip()
        else:
            caption = str(res.content).strip()

        CAPTION_HASH_CACHE[img_hash] = caption
        return f"💡 **AI Caption ({kind}):** {caption}"
    except Exception as e:
        return f"⚠️ Error calling Gemini Vision: {e}"

def extract_pdf(filepath: str, enable_captioning: bool = True, force_reprocess: bool = False) -> str:
    """Master PDF parser entrypoint."""
    try:
        import fitz
    except ImportError:
        return "❌ Error: 'PyMuPDF' package is not installed. Install it with: pip install PyMuPDF"

    if not os.path.exists(filepath):
        return f"❌ Error: File not found at '{filepath}'"

    doc_hash = get_file_md5(filepath)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    cache_dir = os.path.join(base_dir, "Memory", "document_cache", f"cache_{doc_hash[:10]}")
    os.makedirs(cache_dir, exist_ok=True)

    index_json_path = os.path.join(cache_dir, "page_index.json")
    if os.path.exists(index_json_path) and not force_reprocess:
        with open(index_json_path, "r", encoding="utf-8") as f:
            cached_entries = json.load(f)
        
        output_lines = [f"📄 Document: {os.path.basename(filepath)}\n" + "="*50]
        page_dict = {}
        for entry in cached_entries:
            p = entry.get('page', 1)
            page_dict.setdefault(p, []).append(entry)
            
        for page_num in sorted(page_dict.keys()):
            output_lines.append(f"\n--- Page {page_num} ---")
            for entry in page_dict[page_num]:
                content = entry.get("content", "").strip()
                if content and not content.startswith("[Caption skipped"):
                    output_lines.append(content)
        return "\n".join(output_lines)

    doc = fitz.open(filepath)
    all_entries = []
    output_lines = [f"📄 Document: {os.path.basename(filepath)} | Pages: {len(doc)}\n" + "="*50]

    for page_num in range(len(doc)):
        page = doc[page_num]
        output_lines.append(f"\n--- Page {page_num + 1} ---")
        
        # 1. Always extract full page plain text first so text content (schedules, lists) is never lost
        raw_page_text = page.get_text("text").strip()
        if raw_page_text:
            output_lines.append(raw_page_text)
            all_entries.append({"type": "text", "page": page_num + 1, "content": raw_page_text})

        diagram_boxes, image_xrefs = classify_pdf_page(doc, page)

        # 2. Diagrams (Path B)
        for bbox in diagram_boxes:
            x0, y0, x1, y1 = bbox
            margin = 10.0
            rect = fitz.Rect(max(0, x0 - margin), max(0, y0 - margin), min(page.rect.width, x1 + margin), min(page.rect.height, y1 + margin))
            pix = page.get_pixmap(clip=rect, dpi=150)
            img_bytes = pix.tobytes("png")
            img_hash = get_bytes_md5(img_bytes)
            
            crop_path = os.path.join(cache_dir, f"diagram_p{page_num+1}_{img_hash[:8]}.png")
            if not os.path.exists(crop_path):
                pix.save(crop_path)
                
            caption = caption_image_gemini(crop_path, img_hash, kind="diagram") if enable_captioning else ""
            if caption and not caption.startswith("[Caption skipped"):
                all_entries.append({"type": "diagram", "page": page_num + 1, "image_path": crop_path, "content": caption})
                output_lines.append(f"\n🖼️ [Diagram Summary]: {caption}")

        # 3. Embedded Images (Path A)
        for img_info in image_xrefs:
            xref = img_info[0]
            base_img = doc.extract_image(xref)
            img_bytes = base_img.get("image", b"")
            img_ext = base_img.get("ext", "png")
            img_hash = get_bytes_md5(img_bytes)
            
            img_path = os.path.join(cache_dir, f"image_p{page_num+1}_xref{xref}_{img_hash[:8]}.{img_ext}")
            if not os.path.exists(img_path):
                with open(img_path, "wb") as f:
                    f.write(img_bytes)
                    
            caption = caption_image_gemini(img_path, img_hash, kind="image") if enable_captioning else ""
            if caption and not caption.startswith("[Caption skipped"):
                all_entries.append({"type": "image", "page": page_num + 1, "image_path": img_path, "content": caption})
                output_lines.append(f"\n📷 [Image Description]: {caption}")

    with open(index_json_path, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, indent=2)

    return "\n".join(output_lines)
