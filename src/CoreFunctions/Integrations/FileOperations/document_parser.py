"""
Backward-compatibility bridge for document_parsers package.
Redirects to src.CoreFunctions.Integrations.FileOperations.document_parsers.
"""

from .document_parsers import (
    extract_text_from_document,
    extract_pdf,
    extract_docx,
    extract_xlsx,
    extract_pptx,
    extract_text_file
)

__all__ = [
    "extract_text_from_document",
    "extract_pdf",
    "extract_docx",
    "extract_xlsx",
    "extract_pptx",
    "extract_text_file"
]
