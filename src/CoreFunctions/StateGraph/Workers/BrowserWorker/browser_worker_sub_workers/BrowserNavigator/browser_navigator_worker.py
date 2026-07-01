from src.CoreFunctions.StateGraph.registry import BaseWorker
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_prompt import SYSTEM_PROMPT_BROWSER_NAVIGATOR
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_worker_tools import browser_tools
from typing import List


class BrowserNavigator(BaseWorker):
    """Sub-worker private to BrowserWorker.
    Handles browser navigation and click/type interactions.

    NOTE: This class is NOT registered in the global WorkerRegistry.
    It is only accessible through BrowserWorker.sub_workers.
    """
    name = "BrowserNavigator"
    description = "Handles browser navigation and click/type interactions."
    instructions = SYSTEM_PROMPT_BROWSER_NAVIGATOR
    tools = browser_tools
    categories = ["browser", "BrowserNavigator"]
    is_graph_node = False

    @property
    def sub_workers(self) -> List[BaseWorker]:
        """BrowserNavigator has no sub-workers by default."""
        return []
