from .system_worker.worker import SystemWorker
from .communication_worker.worker import CommunicationWorker
from .productivity_worker.worker import ProductivityWorker
from .browser_worker.worker import BrowserWorker
from .github_worker.worker import GithubWorker
from .classroom_worker.worker import ClassroomWorker
from .google_drive_worker.worker import GoogleDriveWorker
from .youtube_worker.worker import YoutubeWorker
from .research_worker.worker import ResearchWorker
from .obsidian_worker.worker import ObsidianWorker
from .memory_worker.worker import MemoryWorker
from .misc_worker.worker import MiscWorker

__all__ = [
    "SystemWorker",
    "CommunicationWorker",
    "ProductivityWorker",
    "BrowserWorker",
    "GithubWorker",
    "ClassroomWorker",
    "GoogleDriveWorker",
    "YoutubeWorker",
    "ResearchWorker",
    "ObsidianWorker",
    "MemoryWorker",
    "MiscWorker"
]
