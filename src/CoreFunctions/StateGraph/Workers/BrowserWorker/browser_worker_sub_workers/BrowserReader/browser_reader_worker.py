from src.CoreFunctions.StateGraph.registry import BaseWorker
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_prompt import SYSTEM_PROMPT_BROWSER_READER
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_worker_tools import browser_tools
from typing import List


class BrowserReader(BaseWorker):
    """Sub-worker private to BrowserWorker.
    Reads and scrapes browser page content.

    NOTE: This class is NOT registered in the global WorkerRegistry.
    It is only accessible through BrowserWorker.sub_workers.
    """
    name = "BrowserReader"
    description = "Reads and scrapes browser page content."
    instructions = SYSTEM_PROMPT_BROWSER_READER
    tools = browser_tools
    categories = ["browser", "BrowserReader"]
    is_graph_node = False

    @property
    def sub_workers(self) -> List[BaseWorker]:
        """BrowserReader has no sub-workers by default."""
        return []
