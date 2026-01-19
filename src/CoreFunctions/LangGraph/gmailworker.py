from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import gmail_tools

def create_gmail_worker(model):
    """
    Creates the GmailWorker node.
    """
    system_prompt = (
        "You are the GmailWorker. "
        "Your capabilities include checking for unread emails and sending emails using Gmail. "
        "Use 'fetch_unread_mails' to check for new messages and 'send_gmail' to compose and send emails. "
        "Provide clear confirmations when emails are sent."
    )

    worker = WorkerAgent(
        model=model,
        tools=gmail_tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node()
