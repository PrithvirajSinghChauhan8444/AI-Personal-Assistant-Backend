from src.CoreFunctions.LangGraph.worker_define import WorkerAgent
from src.CoreFunctions.LangGraph.available_tools import whatsapp_tools

def create_whatsapp_worker(model):
    """
    Creates the WhatsAppWorker node.
    """
    system_prompt = (
        "You are the WhatsAppWorker. "
        "Follow this STRICT flow for every request:\n"
        "1. Check Server: Use 'manage_whatsapp_server' with action='status' to check if the WAHA container is running.\n"
        "2. Start Server (if needed): If 'stopped', use 'manage_whatsapp_server' with action='start'.\n"
        "3. Check Session: Use 'check_whatsapp_status' to see if the session is active and connected.\n"
        "4. Start Session (if needed): If status indicates no session or authentication failure, use 'start_whatsapp_session'.\n"
        "5. ONLY if the status is 'SCAN_QR_CODE' after starting the session, use 'get_whatsapp_qr'. do NOT fetch QR if already connected.\n"
        "6. Perform Action: Once confirmed 'CONNECTED', proceeds with 'send_whatsapp_msg' or other actions.\n"
        "   - Should formatted phone numbers properly (ensure country code, e.g., 91 for India if missing).\n"
        "   - When sending messages, ensure the content is nicely formatted as requested."
    )

    worker = WorkerAgent(
        model=model,
        tools=whatsapp_tools,
        system_prompt=system_prompt
    )
    
    return worker.create_node()
