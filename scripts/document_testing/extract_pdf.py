#!/usr/bin/env python3
"""
Production-Grade PDF Pipeline Extractor:
- Dual-Path Detection (Vector Diagram Clusters vs Embedded Images)
- MD5 Image & Document Hash Deduplication (Idempotency)
- Direct Page Routing Regex (Page == N)
- Cache Retention & Metadata Management
- Optional Gemini Vision Captioning

Usage: python extract_pdf.py <path_to_pdf_file> [--caption] [--output-dir <dir>]
"""

import sys
import os
import re
import json
import base64
import hashlib
from typing import List, Dict, Any, Tuple, Optional

# Global cache dictionary for MD5 image hashes to avoid recaptioning identical images/logos
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
    """
    Filters out tiny junk images (logos, bullets, thin decorative borders).
    """
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
    """
    Scores a cluster of text blocks to determine if it forms a diagram/flowchart.
    Checks for overlapping vector lines/shapes and short fragment labels.
    """
    score = 0
    if not cluster_blocks:
        return 0
    
    cluster_bbox = union_bbox([b["bbox"] for b in cluster_blocks])
    
    # 1. Check for overlapping vector drawings (shapes, lines, arrows)
    overlapping_drawings = sum(1 for d in drawings if is_overlapping(cluster_bbox, d["rect"]))
    if overlapping_drawings > 2:
        score += 2
    elif overlapping_drawings > 0:
        score += 1

    # 2. Check text label characteristic (diagrams contain short labels rather than long paragraphs)
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

def classify_page(doc, page) -> Tuple[List[Tuple[float, float, float, float]], List[Any]]:
    """
    DUAL-PATH CLASSIFICATION:
    Path 1: Vector Diagram Regions (via text clustering + drawing scores)
    Path 2: Embedded Image XRefs (filtered by dimensions & quality)
    """
    import fitz
    import numpy as np
    
    try:
        from sklearn.cluster import DBSCAN
        has_dbscan = True
    except ImportError:
        has_dbscan = False

    text_page = page.get_text("dict")
    text_blocks = [b for b in text_page.get("blocks", []) if b.get("type") == 0]
    drawings = page.get_drawings()
    raw_images = page.get_images(full=True)

    # Filter embedded images using min dimensions
    valid_embedded_images = []
    for img_info in raw_images:
        xref = img_info[0]
        base_img = doc.extract_image(xref)
        if is_valid_image(base_img):
            valid_embedded_images.append(img_info)

    # Check for whole page diagram (slides)
    if is_whole_page_diagram(page, text_blocks, drawings):
        return [(0.0, 0.0, float(page.rect.width), float(page.rect.height))], valid_embedded_images

    diagram_regions = []
    if text_blocks and has_dbscan:
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

def handle_diagram(page, bbox: Tuple[float, float, float, float], output_dir: str, margin: float = 10.0, dpi: int = 150) -> Tuple[str, str]:
    """Crops diagram region and computes its MD5 hash for deduplication."""
    import fitz
    x0, y0, x1, y1 = bbox
    rect = fitz.Rect(max(0, x0 - margin), max(0, y0 - margin), min(page.rect.width, x1 + margin), min(page.rect.height, y1 + margin))
    pix = page.get_pixmap(clip=rect, dpi=dpi)
    img_bytes = pix.tobytes("png")
    img_hash = get_bytes_md5(img_bytes)
    
    filename = f"diagram_p{page.number + 1}_{img_hash[:8]}.png"
    filepath = os.path.join(output_dir, filename)
    if not os.path.exists(filepath):
        pix.save(filepath)
        
    return filepath, img_hash

def handle_embedded_image(doc, xref: int, page_num: int, output_dir: str) -> Tuple[str, str]:
    """Extracts embedded image bytes and computes its MD5 hash for deduplication."""
    base_image = doc.extract_image(xref)
    image_ext = base_image.get("ext", "png")
    image_bytes = base_image.get("image")
    img_hash = get_bytes_md5(image_bytes)
    
    filename = f"image_p{page_num + 1}_xref{xref}_{img_hash[:8]}.{image_ext}"
    filepath = os.path.join(output_dir, filename)
    if not os.path.exists(filepath):
        with open(filepath, "wb") as f:
            f.write(image_bytes)
            
    return filepath, img_hash

def load_environment():
    """Locates and loads .env from project root, config/.env, or current working directory."""
    try:
        from dotenv import load_dotenv
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))
        
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
    """
    Captions image with Gemini Vision LLM. Uses global MD5 hash cache to avoid recaptioning identical images/logos.
    """
    if img_hash in CAPTION_HASH_CACHE:
        return f"💡 **AI Caption ({kind} - Deduplicated)**: {CAPTION_HASH_CACHE[img_hash]}"

    load_environment()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        fallback_msg = f"[Caption skipped: API Key missing in env/config/.env for {os.path.basename(image_path)}]"
        CAPTION_HASH_CACHE[img_hash] = fallback_msg
        return fallback_msg

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
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

        llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.1, google_api_key=api_key)
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

def search_index_with_page_routing(query: str, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    ROUTING REFINEMENT: Parses explicit page numbers (e.g. 'page 3') from the user query
    and directly filters results by page == N, bypassing semantic similarity matching when explicit.
    """
    match = re.search(r'\bpage\s*(\d+)\b', query, re.IGNORECASE)
    if match:
        target_page = int(match.group(1))
        matched_entries = [e for e in entries if e.get("page") == target_page]
        if matched_entries:
            return matched_entries
            
    # Fallback to returning all entries for general semantic search
    return entries

def process_pdf_pipeline(filepath: str, output_dir: str = None, enable_captioning: bool = False, force_reprocess: bool = False) -> str:
    """
    IDEMPOTENT PDF PIPELINE:
    - Keys document cache by file MD5 hash to avoid reprocessing identical files.
    """
    try:
        import fitz
    except ImportError:
        return "❌ Error: 'PyMuPDF' package is not installed. Install it with: pip install PyMuPDF"

    if not os.path.exists(filepath):
        return f"❌ Error: File not found at '{filepath}'"

    doc_hash = get_file_md5(filepath)
    base_name = os.path.splitext(os.path.basename(filepath))[0]

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(filepath), f"cache_{doc_hash[:10]}_{base_name}")

    os.makedirs(output_dir, exist_ok=True)
    index_json_path = os.path.join(output_dir, "page_index.json")

    # IDEMPOTENCY CHECK: If index exists and force_reprocess is False, return cached index instantly!
    if os.path.exists(index_json_path) and not force_reprocess:
        with open(index_json_path, "r", encoding="utf-8") as f:
            cached_entries = json.load(f)
        return f"⚡ [IDEMPOTENT CACHE HIT] Document '{os.path.basename(filepath)}' (Hash: {doc_hash[:10]}) already indexed ({len(cached_entries)} items loaded instantly from {index_json_path})."

    doc = fitz.open(filepath)
    all_entries = []
    summary_report = [
        f"📄 Processing PDF Pipeline: {os.path.basename(filepath)} | Hash: {doc_hash[:10]} | Pages: {len(doc)}",
        f"📁 Cache Directory: {output_dir}",
        "=" * 65
    ]

    for page_num in range(len(doc)):
        page = doc[page_num]
        summary_report.append(f"\n--- PAGE {page_num + 1} ---")
        
        diagram_boxes, image_xrefs = classify_page(doc, page)

        # 1. Diagram Regions (Path B)
        for bbox in diagram_boxes:
            crop_path, img_hash = handle_diagram(page, bbox, output_dir)
            caption = caption_image_gemini(crop_path, img_hash, kind="diagram") if enable_captioning else f"[Diagram crop saved to {os.path.basename(crop_path)}]"
            
            entry = {
                "type": "diagram",
                "page": page_num + 1,
                "bbox": bbox,
                "image_path": crop_path,
                "image_hash": img_hash,
                "content": caption
            }
            all_entries.append(entry)
            summary_report.append(f"🖼️ [Diagram Region] BBox: {bbox} -> Hash: {img_hash[:8]}\n   Caption: {caption}")

        # 2. Embedded Images (Path A)
        for img_info in image_xrefs:
            xref = img_info[0]
            img_path, img_hash = handle_embedded_image(doc, xref, page_num, output_dir)
            caption = caption_image_gemini(img_path, img_hash, kind="image") if enable_captioning else f"[Embedded Image saved to {os.path.basename(img_path)}]"
            
            entry = {
                "type": "image",
                "page": page_num + 1,
                "xref": xref,
                "image_path": img_path,
                "image_hash": img_hash,
                "content": caption
            }
            all_entries.append(entry)
            summary_report.append(f"📷 [Embedded Image] XRef: {xref} -> Hash: {img_hash[:8]}\n   Caption: {caption}")

        # 3. Paragraph Text (deduplicated against diagram bounding boxes)
        text_dict = page.get_text("dict")
        text_blocks = [b for b in text_dict.get("blocks", []) if b.get("type") == 0]
        
        page_paragraphs = []
        for b in text_blocks:
            in_diagram = any(is_inside_box(b["bbox"], d_box) for d_box in diagram_boxes)
            if not in_diagram:
                plain_text = "".join(span["text"] for line in b.get("lines", []) for span in line.get("spans", [])).strip()
                if plain_text:
                    page_paragraphs.append(plain_text)

        if page_paragraphs:
            combined_text = "\n".join(page_paragraphs)
            all_entries.append({
                "type": "text",
                "page": page_num + 1,
                "content": combined_text
            })
            summary_report.append(f"📝 [Paragraph Text] ({len(page_paragraphs)} blocks):\n{combined_text}")

    # Save structured index
    with open(index_json_path, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, indent=2)

    summary_report.append("\n" + "=" * 65)
    summary_report.append(f"✅ Pipeline Complete! Indexed {len(all_entries)} total items. Saved index to {index_json_path}")
    
    return "\n".join(summary_report)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_pdf.py <path_to_pdf_file> [--caption] [--reprocess]")
        sys.exit(1)

    target_pdf = sys.argv[1]
    do_caption = "--caption" in sys.argv
    do_reprocess = "--reprocess" in sys.argv

    result = process_pdf_pipeline(target_pdf, enable_captioning=do_caption, force_reprocess=do_reprocess)
    print(result)
