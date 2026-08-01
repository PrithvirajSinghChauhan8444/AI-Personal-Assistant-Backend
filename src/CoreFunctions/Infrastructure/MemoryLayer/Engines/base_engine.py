from typing import List, Dict, Any, Optional

class BaseMemoryEngine:
    """Abstract Base Class defining the standard interface for all memory cache backends."""

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int = 1800) -> None:
        raise NotImplementedError

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def keys(self, pattern: str) -> List[str]:
        raise NotImplementedError

    def acquire_lock(self, lock_name: str, lease_time: int = 5) -> bool:
        raise NotImplementedError

    def release_lock(self, lock_name: str) -> None:
        raise NotImplementedError
