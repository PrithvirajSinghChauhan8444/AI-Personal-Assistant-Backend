import os

def get_config_path(filename: str) -> str:
    """
    Returns the absolute path to a file inside the global 'config' folder.
    Works no matter where the script is run from.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))  # goes up from /src/CoreFunctions/Infrastructure/
    config_dir = os.path.join(base_dir, "config")
    return os.path.join(config_dir, filename)
