from CoreFunctions.Integrations.Gmail.read_unread import fetch_unread_emails_detailed

def handle_gmail_command(user_input, page_token=None): # <-- 1. Accept page_token
    """
    Handles all Gmail-related commands.
    """
    if "check" in user_input and ("unread" in user_input or "mail" in user_input):
        
        # --- 2. Pass the token ---
        return fetch_unread_emails_detailed(page_token)
    
    return {"error": "Unknown Gmail command"}