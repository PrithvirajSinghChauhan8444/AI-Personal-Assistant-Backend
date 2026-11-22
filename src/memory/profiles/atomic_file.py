"""Atomic file persistence utilities for memory profiles."""

import os
import tempfile


def atomic_write_text(file_path: str, content: str, encoding: str = "utf-8") -> None:
    """Atomically writes text to file_path using a temporary file and atomic rename."""
    dir_name = os.path.dirname(os.path.abspath(os.path.expanduser(file_path)))
    os.makedirs(dir_name, exist_ok=True)

    temp_file = tempfile.NamedTemporaryFile(
        dir=dir_name,
        delete=False,
        suffix=".tmp",
        mode="w",
        encoding=encoding,
    )
    temp_path = temp_file.name

    try:
        temp_file.write(content)
        temp_file.flush()
        temp_file.close()
        os.replace(temp_path, file_path)
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise
