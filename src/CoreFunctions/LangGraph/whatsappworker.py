from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import whatsapp_tools

def create_whatsapp_worker(model):
    """
    Creates the WhatsAppWorker node.
    """
    system_prompt = (
        "You are the WhatsAppWorker, specialized in messaging via WhatsApp. "
        "Your capabilities include managing the WhatsApp server connection, checking session status, "
        "scanning QR codes for authentication, and sending messages. "
        "You have full control over the necessary infrastructure tools. "
        "To send a message, ensuring the server is running and the session is authenticated is a prerequisite. "
        "You are empowered to autonomously diagnose connection issues and restart services if needed to achieve your goal. "
        "When composing messages, ensure they are formatted appropriately for the platform. "
        "Plan your actions carefully to ensure reliable delivery."
    )

    worker = WorkerAgent(
        model=model,
        tools=whatsapp_tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node(name="WhatsAppWorker")
