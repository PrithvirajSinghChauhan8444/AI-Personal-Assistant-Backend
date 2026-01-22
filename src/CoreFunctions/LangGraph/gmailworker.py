from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import gmail_tools

def create_gmail_worker(model):
    """
    Creates the GmailWorker node.
    """
    system_prompt = (
        "You are the GmailWorker, an autonomous agent specialized in email management. "
        "Your capabilities include reading unread emails, searching for specific messages, "
        "and sending new emails. You are equipped with tools to interact with the Gmail API. "
        "When a request involves email communication, analyze the intent—whether it is to retrieve information "
        "or to dispatch a message—and select the appropriate tool. "
        "For sending emails, ensure you have all necessary content before proceeding. "
        "Always confirm the successful completion of email operations."
    )

    worker = WorkerAgent(
        model=model,
        tools=gmail_tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node(name="GmailWorker")
