"""Cross-process re-entrant file lock backed by fcntl.flock."""

import contextlib
import fcntl
import os
from typing import Iterator, Optional


class ProcessLock:
    """Re-entrant cross-process file lock protecting shared disk resources."""

    def __init__(self, lock_path: str) -> None:
        self.lock_path = os.path.abspath(os.path.expanduser(lock_path))
        self._lock_depth: int = 0
        self._lock_file: Optional[object] = None
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)

    @contextlib.contextmanager
    def acquire(self) -> Iterator[None]:
        """Context manager for acquiring and releasing the file lock."""
        if self._lock_depth > 0:
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1
            return

        self._lock_file = open(self.lock_path, "w")
        fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX)
        self._lock_depth = 1
        try:
            yield
        finally:
            self._lock_depth = 0
            try:
                if self._lock_file is not None:
                    fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                    self._lock_file.close()
            except Exception:
                pass
            self._lock_file = None
