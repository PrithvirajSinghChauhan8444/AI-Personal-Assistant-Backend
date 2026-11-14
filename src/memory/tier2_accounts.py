"""Tier 2 Connected Accounts and Personal Context Manager for Layer 5."""

import json
import os
from typing import Any, Dict, List, Optional

DEFAULT_ACCOUNTS_DATA: Dict[str, Any] = {
    "primary_user": "User",
    "email_accounts": [],
    "communication_handles": {},
    "preferences": {
        "preferred_email_alias": "primary",
        "default_timezone": "UTC",
    },
}


class AccountsContextManager:
    """Manages reading, updating, and formatting ~/.config/ai-assistant/memory/accounts.json."""

    def __init__(self, file_path: str) -> None:
        self.file_path = os.path.abspath(os.path.expanduser(file_path))
        self._data: Dict[str, Any] = {}
        self._ensure_file_exists()
        self.load()

    def _ensure_file_exists(self) -> None:
        """Initializes default accounts.json on disk if not present."""
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_ACCOUNTS_DATA, f, indent=2)

    def load(self) -> None:
        """Reads accounts.json from disk."""
        if not os.path.isfile(self.file_path):
            self._data = dict(DEFAULT_ACCOUNTS_DATA)
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = dict(DEFAULT_ACCOUNTS_DATA)

    def save(self) -> None:
        """Saves current accounts state to disk."""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get_accounts_data(self) -> Dict[str, Any]:
        """Returns raw account dictionary."""
        return dict(self._data)

    def get_accounts_summary(self) -> str:
        """Formats the accounts into a clean context prompt block."""
        lines = ["# User Accounts & Connected Context"]
        primary_user = self._data.get("primary_user", "User")
        lines.append(f"- User: {primary_user}")

        emails: List[Dict[str, Any]] = self._data.get("email_accounts", [])
        if emails:
            lines.append("- Email Accounts:")
            for email in emails:
                alias = email.get("alias", "unknown")
                addr = email.get("email", "")
                provider = email.get("provider", "")
                lines.append(f"  * [{alias}] {addr} ({provider})")

        handles: Dict[str, str] = self._data.get("communication_handles", {})
        if handles:
            lines.append("- Connected Channels:")
            for platform, handle in handles.items():
                lines.append(f"  * {platform.capitalize()}: {handle}")

        prefs: Dict[str, Any] = self._data.get("preferences", {})
        if prefs:
            lines.append("- Personal Scopes:")
            for k, v in prefs.items():
                lines.append(f"  * {k}: {v}")

        return "\n".join(lines)

    def update_account(self, alias: str, email: str, provider: str = "google", scopes: Optional[List[str]] = None) -> None:
        """Upserts an email account alias."""
        emails = self._data.setdefault("email_accounts", [])
        for item in emails:
            if item.get("alias") == alias:
                item["email"] = email
                item["provider"] = provider
                if scopes is not None:
                    item["scopes"] = scopes
                self.save()
                return

        emails.append({
            "alias": alias,
            "email": email,
            "provider": provider,
            "scopes": scopes or ["default"],
        })
        self.save()

    def update_handle(self, platform: str, handle: str) -> None:
        """Upserts a communication handle (telegram, discord, etc.)."""
        handles = self._data.setdefault("communication_handles", {})
        handles[platform.lower()] = handle
        self.save()
