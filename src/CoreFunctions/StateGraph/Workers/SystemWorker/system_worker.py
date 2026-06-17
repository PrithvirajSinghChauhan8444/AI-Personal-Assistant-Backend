from src.CoreFunctions.StateGraph.registry import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.SystemWorker.system_prompt import SYSTEM_PROMPT
from src.CoreFunctions.StateGraph.Workers.SystemWorker.system_tools import system_tools

@WorkerRegistry.register
class SystemWorker(BaseWorker):
    name = "SystemWorker"
    description = "Handles OS terminal commands, file management, scripts, system health, and worker/agent configuration/listing. It is the ONLY worker with local file system write/read permissions."
    instructions = SYSTEM_PROMPT
    tools = system_tools
    categories = ["system-management", "system-monitoring", "system-automation", "SystemWorker"]
