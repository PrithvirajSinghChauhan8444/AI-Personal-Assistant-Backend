"""
Document Parsers Package.
Exports unified document extraction entrypoint supporting PDFs, Word, Excel, PowerPoint, Text files, and Standalone Images.
"""

import os
from .pdf_parser import extract_pdf
from .docx_parser import extract_docx
from .xlsx_parser import extract_xlsx
from .pptx_parser import extract_pptx
from .text_parser import extract_text_file
from .image_parser import extract_image_file

def extract_text_from_document(filepath: str) -> str:
    """
    Master unified parser function.
    Detects document extension and uses appropriate extraction strategy.
    """
    if not os.path.exists(filepath):
        return f"❌ Error: File not found at '{filepath}'"

    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    if ext == ".pdf":
        return extract_pdf(filepath)
    elif ext in [".docx", ".doc"]:
        return extract_docx(filepath)
    elif ext in [".xlsx", ".xls"]:
        return extract_xlsx(filepath)
    elif ext in [".pptx", ".ppt"]:
        return extract_pptx(filepath)
    elif ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]:
        return extract_image_file(filepath)
    else:
        return extract_text_file(filepath)

__all__ = [
    "extract_text_from_document",
    "extract_pdf",
    "extract_docx",
    "extract_xlsx",
    "extract_pptx",
    "extract_image_file",
    "extract_text_file"
]
