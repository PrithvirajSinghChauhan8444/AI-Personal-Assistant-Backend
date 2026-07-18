"""
Plain Text File Parser Module.
Reads standard text, code, and config files (.txt, .md, .py, .json, .csv, etc.).
"""

import os

def extract_text_file(filepath: str) -> str:
    """Reads standard text files using UTF-8 encoding."""
    if not os.path.exists(filepath):
        return f"❌ Error: File not found at '{filepath}'"

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"❌ Error reading text file '{filepath}': {e}"
