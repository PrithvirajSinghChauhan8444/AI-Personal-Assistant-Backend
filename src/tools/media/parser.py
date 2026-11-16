"""Unified local document and media parsing engine.

Extracts structured Markdown content from PDF, DOCX, XLSX, PPTX, CSV, and Images.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ParsedDocument:
    file_path: str
    file_type: str
    title: str
    total_pages: int
    content: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_pdf_document(file_path: str, max_pages: int = 50) -> ParsedDocument:
    """Extract page text and tables from a PDF document using PyMuPDF."""
    import fitz

    doc = fitz.open(file_path)
    page_count = len(doc)
    limit = min(page_count, max_pages)
    sections: List[str] = []

    for page_num in range(limit):
        page = doc[page_num]
        page_text = page.get_text("text").strip()
        if page_text:
            sections.append(f"## Page {page_num + 1}\n\n{page_text}")

    content = "\n\n".join(sections)
    if limit < page_count:
        content += f"\n\n*[Truncated: showing first {limit} of {page_count} pages]*"

    title = doc.metadata.get("title") or os.path.basename(file_path)
    return ParsedDocument(
        file_path=file_path,
        file_type="pdf",
        title=title,
        total_pages=page_count,
        content=content,
    )


def parse_docx_document(file_path: str) -> ParsedDocument:
    """Extract paragraphs and tables from a Word document as Markdown."""
    import docx

    doc = docx.Document(file_path)
    lines: List[str] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if para.style.name.startswith("Heading 1"):
            lines.append(f"# {text}")
        elif para.style.name.startswith("Heading 2"):
            lines.append(f"## {text}")
        elif para.style.name.startswith("Heading 3"):
            lines.append(f"### {text}")
        else:
            lines.append(text)

    for table_idx, table in enumerate(doc.tables):
        lines.append(f"\n### Table {table_idx + 1}")
        for row in table.rows:
            row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            lines.append("| " + " | ".join(row_cells) + " |")

    return ParsedDocument(
        file_path=file_path,
        file_type="docx",
        title=os.path.basename(file_path),
        total_pages=1,
        content="\n\n".join(lines),
    )


def parse_sheet_document(file_path: str, max_rows: int = 100) -> ParsedDocument:
    """Extract spreadsheet sheets and cells as Markdown tables."""
    import openpyxl

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    sections: List[str] = []

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        sections.append(f"## Sheet: {sheet_name}")
        rows = list(sheet.iter_rows(max_row=max_rows, values_only=True))
        if not rows:
            sections.append("*(empty sheet)*")
            continue

        header = [str(val or "") for val in rows[0]]
        sections.append("| " + " | ".join(header) + " |")
        sections.append("| " + " | ".join(["---"] * len(header)) + " |")

        for row in rows[1:]:
            row_vals = [str(val or "") for val in row]
            sections.append("| " + " | ".join(row_vals) + " |")

        if sheet.max_row and sheet.max_row > max_rows:
            sections.append(f"\n*[Showing first {max_rows} of {sheet.max_row} rows]*")

    return ParsedDocument(
        file_path=file_path,
        file_type="xlsx",
        title=os.path.basename(file_path),
        total_pages=len(wb.sheetnames),
        content="\n\n".join(sections),
    )


def parse_csv_document(file_path: str, max_rows: int = 100) -> ParsedDocument:
    """Extract delimited CSV data into a Markdown table."""
    lines: List[str] = []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        rows = []
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append(row)

    if not rows:
        return ParsedDocument(file_path, "csv", os.path.basename(file_path), 1, "*(empty csv)*")

    header = rows[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return ParsedDocument(
        file_path=file_path,
        file_type="csv",
        title=os.path.basename(file_path),
        total_pages=1,
        content="\n".join(lines),
    )


def parse_presentation_document(file_path: str) -> ParsedDocument:
    """Extract slide titles and bullet points from PowerPoint presentations."""
    from pptx import Presentation

    prs = Presentation(file_path)
    sections: List[str] = []

    for idx, slide in enumerate(prs.slides):
        slide_lines: List[str] = [f"## Slide {idx + 1}"]
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        slide_lines.append(f"- {text}")
        sections.append("\n".join(slide_lines))

    return ParsedDocument(
        file_path=file_path,
        file_type="pptx",
        title=os.path.basename(file_path),
        total_pages=len(prs.slides),
        content="\n\n".join(sections),
    )


def parse_image_metadata(file_path: str) -> ParsedDocument:
    """Extract dimensions, color mode, and format details from an image."""
    from PIL import Image

    with Image.open(file_path) as img:
        info_lines = [
            f"# Image: {os.path.basename(file_path)}",
            f"- **Format:** {img.format}",
            f"- **Dimensions:** {img.width}x{img.height} px",
            f"- **Color Mode:** {img.mode}",
        ]
        return ParsedDocument(
            file_path=file_path,
            file_type="image",
            title=os.path.basename(file_path),
            total_pages=1,
            content="\n".join(info_lines),
        )


def parse_document(file_path: str, max_pages: int = 50) -> ParsedDocument:
    """Detect file format and route to dedicated parser."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return parse_pdf_document(file_path, max_pages=max_pages)
    if ext in (".docx", ".doc"):
        return parse_docx_document(file_path)
    if ext in (".xlsx", ".xls"):
        return parse_sheet_document(file_path)
    if ext == ".csv":
        return parse_csv_document(file_path)
    if ext in (".pptx", ".ppt"):
        return parse_presentation_document(file_path)
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        return parse_image_metadata(file_path)

    raise ValueError(f"Unsupported file format: {ext}")


def main():
    parser = argparse.ArgumentParser(description="Parse document to structured Markdown")
    parser.add_argument("path", help="Path to document file")
    parser.add_argument("--json", action="store_true", help="Output JSON structure")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages to parse")
    args = parser.parse_args()

    try:
        parsed = parse_document(args.path, max_pages=args.max_pages)
        if args.json:
            print(json.dumps(parsed.to_dict(), indent=2))
        else:
            print(parsed.content)
    except Exception as exc:
        sys.stderr.write(f"Parsing error: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
