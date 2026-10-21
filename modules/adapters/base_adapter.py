from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseAdapter(ABC):
    """
    Standard interface contract for presentation and client adapters
    (CLI, Telegram, Web, Discord, etc.).
    Ensures zero coupling between core cognitive engine and transport channels.
    """

    @abstractmethod
    def start(self) -> None:
        """Start the adapter listener or event loop."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Gracefully stop the adapter."""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Check if the adapter is actively running."""
        pass
