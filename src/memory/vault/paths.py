"""Path resolution and safety validation for the Markdown Knowledge Vault."""

import os
from pathlib import Path
from typing import Optional


def resolve_vault_dir(custom_path: Optional[str] = None) -> Path:
    """Resolves the root directory for the Markdown Vault from config or environment."""
    if custom_path:
        return Path(os.path.expanduser(os.path.expandvars(custom_path))).resolve()

    env_dir = os.environ.get("AI_ASSISTANT_MEMORY_DIR")
    if env_dir:
        return Path(os.path.expanduser(os.path.expandvars(env_dir))).resolve()

    try:
        from src.agents.factory import load_system_config

        cfg = load_system_config()
        if cfg.get("memory_dir"):
            return Path(os.path.expanduser(os.path.expandvars(cfg["memory_dir"]))).resolve()
        if cfg.get("workspace_dir"):
            return Path(os.path.expanduser(os.path.expandvars(cfg["workspace_dir"]))) / "Memory"
    except Exception:
        pass

    return Path.home() / ".config" / "ai-assistant" / "memory"


def safe_vault_path(root_dir: Path, relative_path: str) -> Path:
    """Validates and bounds a relative path strictly within the vault root."""
    clean = Path(relative_path.strip()).as_posix().lstrip("/")
    resolved = (root_dir / clean).resolve()
    if not str(resolved).startswith(str(root_dir)):
        raise ValueError(f"Path traversal detected: {relative_path}")
    return resolved
