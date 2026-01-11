import os

# --- Configuration ---
BASE_URL = "http://localhost:8085"

def load_env_vars():
    """
    Load environment variables from .env file manually.
    Handles stripping quotes to prevent 'Unauthorized' errors.
    """
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    api_key = "secretKEY123" # Default fallback
    
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                # parsing logic: ignore comments, look for KEY=VALUE
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key == "WAHA_API_KEY":
                        # CRITICAL FIX: Strip whitespace AND quotes (' or ")
                        api_key = value.strip().strip('"').strip("'")
                        break
    return api_key

API_KEY = load_env_vars()

def get_headers():
    return {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json"
    }
