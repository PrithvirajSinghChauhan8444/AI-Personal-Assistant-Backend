#!/usr/bin/env python3
"""
Master Document Text Extractor script.
Automatically selects the appropriate parser based on file extension.
Usage: python run_all.py <path_to_document> [--caption]
"""

import sys
import os

from extract_pdf import process_pdf_pipeline
from extract_docx import extract_docx
from extract_xlsx import extract_xlsx
from extract_pptx import extract_pptx

def extract_any(filepath: str, enable_captioning: bool = False) -> str:
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    
    if ext == ".pdf":
        return process_pdf_pipeline(filepath, enable_captioning=enable_captioning)
    elif ext in [".docx", ".doc"]:
        return extract_docx(filepath)
    elif ext in [".xlsx", ".xls"]:
        return extract_xlsx(filepath)
    elif ext in [".pptx", ".ppt"]:
        return extract_pptx(filepath)
    else:
        # Fallback to plain text read
        if not os.path.exists(filepath):
            return f"❌ Error: File not found at '{filepath}'"
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return f"📄 Text Document: {os.path.basename(filepath)}\n" + "="*50 + f"\n{content}"
        except Exception as e:
            return f"❌ Error reading text file: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_all.py <path_to_document> [--caption]")
        sys.exit(1)

    target_path = sys.argv[1]
    do_caption = "--caption" in sys.argv
    print(extract_any(target_path, enable_captioning=do_caption))
