from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import gmail_tools

def create_gmail_worker(model):
    """
    Creates the GmailWorker node.
    """
    system_prompt = (
        "You are the GmailWorker. Your role is email management (read, search, send).\n"
        "Analyze the request, select the best tool, and execute.\n"
        "Always report results clearly and concisely.\n\n"
        "### EXAMPLES\n"
        "User: 'Any new emails?'\n"
        "Action: calls `get_unread_emails` -> 'You have 3 new emails: [Subject 1, Subject 2...]'\n\n"
        "User: 'Search for flight tickets'\n"
        "Action: calls `search_emails(query='flight ticket')` -> 'Found 2 emails regarding flights.'\n\n"
        "User: 'Email boss@co.com that I am late'\n"
        "Action: calls `send_mail(...)` -> 'Emeail sent successfully to boss@co.com.'"
    )

    worker = WorkerAgent(
        model=model,
        tools=gmail_tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node(name="GmailWorker")
