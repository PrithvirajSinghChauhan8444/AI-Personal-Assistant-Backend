from typing import List
from src.CoreFunctions.StateGraph.worker_framework import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_prompt import SYSTEM_PROMPT
from src.CoreFunctions.StateGraph.Workers.GmailWorker.gmail_worker_tools import gmail_tools

@WorkerRegistry.register
class GmailWorker(BaseWorker):
    name = "GmailWorker"
    description = "Reads, searches, and sends emails."
    instructions = SYSTEM_PROMPT
    tools = gmail_tools
    categories = ["communication", "GmailWorker"]

    @property
    def routing_rules(self) -> List[str]:
        return [
            "**Gmail Operations & Email Management Workflow**:\n"
            "   - Any requests related to email management, reading emails, sending messages/drafts, or replying to threads MUST be routed to GmailWorker.\n"
            "   - This includes handling incoming email notifications (proactive runs triggered by Gmail IDLE) to read their full contents, assess whether they require a reply, and draft/send appropriate responses.",
            "**Incoming Email Notification Assessor**:\n"
            "   - When an email is received, route to GmailWorker first to analyze and draft/create replies or take action safely."
        ]
