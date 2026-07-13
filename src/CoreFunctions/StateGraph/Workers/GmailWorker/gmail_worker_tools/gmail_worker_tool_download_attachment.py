import os
import json
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Integrations.Gmail.gmail_attachments import download_gmail_attachment

def download_attachment(email_id: str, attachment_id: str, filename: str, save_dir: str = None, account: str = "personal") -> str:
    """Downloads a specific attachment from an email to a specified directory.
    
    Args:
        email_id (str): The unique message/email ID.
        attachment_id (str): The unique ID of the attachment (found via read_email_content).
        filename (str): The name to save the file as.
        save_dir (str): The directory to save the file to. Defaults to the AGENT_WORKSPACE environment variable if not provided.
        account (str): The target Google account, either 'personal' or 'college' or 'any_other' . Defaults to 'personal'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: download_attachment")
    
    if save_dir is None:
        save_dir = os.environ.get("AGENT_WORKSPACE", "/home/prit/Project_Linux/Assistant_Foler")
        
    try:
        res = download_gmail_attachment(
            email_id=email_id,
            attachment_id=attachment_id,
            filename=filename,
            save_dir=save_dir,
            account=account
        )
        return json.dumps({"status": "success", "message": res})
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})

gmail_worker_tool_download_attachment = StructuredTool.from_function(
    func=download_attachment,
    name="download_attachment",
    description="Downloads a specific attachment from a Gmail email message to a specified folder."
)
