import os
from dotenv import load_dotenv
from CoreFunctions.path_utils import get_config_path
from CoreFunctions.command_handler import handle_text_command
from Apps.Gmail.gmail_handler import handle_gmail_command

# ✅ Load .env from config/
load_dotenv(get_config_path(".env"))

# --- Define keyword sets for intent recognition ---

# Keywords that strongly imply an *action* to check mail
GMAIL_ACTION_WORDS = {
    'check', 'read', 'show', 'get', 'fetch', 
    'how many', 'any new', "what's new"
}

# Keywords that specify the *target* of the action
GMAIL_TARGET_WORDS = {'gmail', 'email', 'mail', 'mails', 'inbox'}


def has_gmail_intent(text: str) -> bool:
    """
    Checks if the user's input shows a clear intent to check mail.
    This is much more robust than simple keyword matching.
    """
    # Create a set of all unique words in the input for fast checks
    input_words = set(text.split())
    
    # --- Check for high-confidence phrases first ---
    # These phrases are almost always about checking mail
    if "what's new" in text or "any new" in text:
        # Check if a target word is also present to be sure
        # e.g., "what's new in my inbox"
        if not GMAIL_TARGET_WORDS.isdisjoint(input_words):
            return True

    # --- Check for the main logic: Action + Target ---
    
    # .isdisjoint() returns True if they have *no* words in common
    # So, `not .isdisjoint()` means there is at least one match.
    has_action = not GMAIL_ACTION_WORDS.isdisjoint(input_words)
    has_target = not GMAIL_TARGET_WORDS.isdisjoint(input_words)

    # Only trigger if the user provides BOTH an action and a target
    # e.g., "check" (action) + "mail" (target)
    return has_action and has_target


def main():
    print("🤖 AI Personal Assistant — Gemini 2.5 Flash")
    print("Commands: summarize <text>, check unread gmail, or chat.\n")

    while True:
        user_input = input("You: ").strip().lower()

        if user_input in ["exit", "quit"]:
            print("👋 Goodbye!")
            break

        # --- Improved Intent Logic ---
        
        # 1. Check for the most specific command first: "summarize"
        # This command is unambiguous and should be handled by handle_text_command.
        if user_input.startswith("summarize "):
            response = handle_text_command(user_input)
        
        # 2. Check for "check mail" intent using our new function
        elif has_gmail_intent(user_input):
            response = handle_gmail_command(user_input)
        
        # 3. Default to general text/chat command
        # This now correctly handles "tell me a joke about email"
        # because it will fail the `has_gmail_intent` check.
        else:
            response = handle_text_command(user_input)

        print(f"Assistant: {response}\n")

if __name__ == "__main__":
    main()