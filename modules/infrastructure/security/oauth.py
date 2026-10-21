import os
import json
from typing import Optional, Dict, Any
from google.oauth2.credentials import Credentials

def get_config_dir() -> str:
    """Locates the config folder."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    config_dir = os.path.join(base_dir, "config")
    if os.path.exists(config_dir):
        return config_dir
    return base_dir

def load_google_accounts() -> Dict[str, str]:
    """Dynamically loads mapped Google accounts from google_accounts.json."""
    config_dir = get_config_dir()
    accounts_path = os.path.join(config_dir, "google_accounts.json")
    if os.path.exists(accounts_path):
        try:
            with open(accounts_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"⚠️ [OAuth] Error loading google_accounts.json: {e}")
    return {}

def resolve_expected_email(account: str) -> str:
    """
    Resolves expected email address for a given account alias or raw email address.
    Raises ValueError with dynamic configured accounts list if alias is not mapped,
    allowing caller and LLM agents to receive structured diagnostic feedback.
    """
    if "@" in account:
        return account.strip().lower()

    accounts = load_google_accounts()
    account_key = account.strip().lower()

    if account_key in accounts and accounts[account_key].strip():
        return accounts[account_key].strip().lower()

    # Alias not mapped. Format dynamic diagnostic error for LLM self-correction
    available_list = [f"'{alias}' ({email})" if email else f"'{alias}'" for alias, email in accounts.items() if alias]
    available_str = ", ".join(available_list) if available_list else "None configured"
    raise ValueError(
        f"Google account alias '{account}' is not recognized or configured in google_accounts.json. "
        f"Available configured accounts: [{available_str}]. "
        "Please choose from the available configured accounts based on the context of the task, or provide a valid email address."
    )

def get_google_credentials(account: str = "personal") -> Optional[Credentials]:
    """Retrieves and decrypts valid Google OAuth credentials for the specified account."""
    try:
        from src.CoreFunctions.Infrastructure.auth_utils import get_valid_credentials
        return get_valid_credentials(account)
    except Exception as e:
        print(f"⚠️ [OAuth Infrastructure] Failed to load credentials for '{account}': {e}")
        return None
