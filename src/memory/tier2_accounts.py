"""Tier 2 Connected Accounts and Personal Context Manager for Layer 5 (Markdown-backed)."""

import json
import os
import re
from typing import Any, Dict, List, Optional

DEFAULT_ACCOUNTS_MD = """# User Accounts & Connected Context

## Primary User
- Name: User

## Email Accounts

## Communication Handles
- Telegram: @handle

## Preferences
- preferred_email_alias: email1
- default_timezone: UTC
"""


class AccountsContextManager:
    """Manages reading, updating, and formatting Markdown-based accounts (accounts.md)."""

    def __init__(self, file_path: str) -> None:
        self.raw_path = os.path.abspath(os.path.expanduser(file_path))
        # Support both accounts.md and legacy accounts.json paths
        if self.raw_path.endswith(".json"):
            self.json_path = self.raw_path
            self.md_path = self.raw_path[:-5] + ".md"
        else:
            self.md_path = self.raw_path
            self.json_path = (
                self.raw_path[:-3] + ".json"
                if self.raw_path.endswith(".md")
                else self.raw_path + ".json"
            )

        self.file_path = self.md_path
        self._primary_user: str = "User"
        self._email_accounts: List[Dict[str, Any]] = []
        self._communication_handles: Dict[str, str] = {}
        self._preferences: Dict[str, str] = {
            "preferred_email_alias": "email1",
            "default_timezone": "UTC",
        }

        self._ensure_file_exists()
        self.load()

    def _ensure_file_exists(self) -> None:
        """Initializes default accounts.md on disk, migrating from accounts.json if present."""
        if os.path.isfile(self.md_path):
            return

        os.makedirs(os.path.dirname(self.md_path), exist_ok=True)

        # Check if legacy accounts.json exists to migrate
        if os.path.isfile(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._import_from_dict(data)
                self.save()
                return
            except Exception:
                pass

        # Also check config/google_accounts.json for initial seed if available
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(self.md_path)))
        config_google = os.path.join(base_dir, "config", "google_accounts.json")
        if os.path.isfile(config_google):
            try:
                with open(config_google, "r", encoding="utf-8") as f:
                    google_map = json.load(f)
                if isinstance(google_map, dict):
                    for alias, email in google_map.items():
                        if email and "@" in email:
                            self._email_accounts.append({
                                "alias": alias.strip().lower(),
                                "email": email.strip().lower(),
                                "provider": "google",
                                "scopes": ["default"],
                            })
                    self.save()
                    return
            except Exception:
                pass

        # Write clean default markdown
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write(DEFAULT_ACCOUNTS_MD)

        # If a json path was explicitly provided, also write json mirror
        if self.raw_path.endswith(".json"):
            try:
                with open(self.raw_path, "w", encoding="utf-8") as f:
                    json.dump(self.get_accounts_data(), f, indent=2)
            except Exception:
                pass

    def _import_from_dict(self, data: Dict[str, Any]) -> None:
        """Imports structured account dictionary."""
        self._primary_user = data.get("primary_user", "User")
        self._email_accounts = list(data.get("email_accounts", []))
        self._communication_handles = dict(data.get("communication_handles", {}))
        self._preferences = dict(data.get("preferences", {}))
        if "preferred_email_alias" not in self._preferences:
            self._preferences["preferred_email_alias"] = "email1"

    def load(self) -> None:
        """Reads and parses accounts.md from disk."""
        target_path = self.md_path if os.path.isfile(self.md_path) else self.json_path
        if not os.path.isfile(target_path):
            return

        if target_path.endswith(".json"):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._import_from_dict(data)
                return
            except Exception:
                pass

        try:
            with open(self.md_path, "r", encoding="utf-8") as f:
                content = f.read()
            self._parse_markdown(content)
        except Exception:
            pass

    def _parse_markdown(self, content: str) -> None:
        """Parses accounts markdown sections into structured state."""
        self._email_accounts.clear()
        self._communication_handles.clear()
        self._preferences.clear()

        current_section = "General"
        lines = content.splitlines()

        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("# "):
                continue

            if line.startswith("## "):
                current_section = line[3:].strip().lower()
                continue

            if not line.startswith("- ") and not line.startswith("* "):
                continue

            item = line[2:].strip()

            if "primary user" in current_section:
                if ":" in item:
                    _, val = item.split(":", 1)
                    if val.strip():
                        self._primary_user = val.strip()

            elif "email" in current_section or "account" in current_section:
                # Format: - [alias] email@example.com (provider)
                # Or: - alias: email@example.com
                match = re.match(r"^\[([a-zA-Z0-9_\-\.]+)\]\s*([^\s\(]+)(?:\s*\(([^\)]+)\))?", item)
                if match:
                    alias = match.group(1).strip().lower()
                    email = match.group(2).strip().lower()
                    provider = match.group(3).strip().lower() if match.group(3) else "google"
                    self._email_accounts.append({
                        "alias": alias,
                        "email": email,
                        "provider": provider,
                        "scopes": ["default"],
                    })
                elif ":" in item:
                    k, v = item.split(":", 1)
                    alias = k.strip().lower()
                    email = v.strip().lower()
                    if "@" in email:
                        self._email_accounts.append({
                            "alias": alias,
                            "email": email,
                            "provider": "google",
                            "scopes": ["default"],
                        })

            elif "communication" in current_section or "handle" in current_section or "channel" in current_section:
                if ":" in item:
                    k, v = item.split(":", 1)
                    self._communication_handles[k.strip().lower()] = v.strip()

            elif "preference" in current_section or "scope" in current_section:
                if ":" in item:
                    k, v = item.split(":", 1)
                    self._preferences[k.strip()] = v.strip()

    def save(self) -> None:
        """Saves current accounts state to accounts.md (and mirror json if needed)."""
        lines = [
            "# User Accounts & Connected Context",
            "",
            "## Primary User",
            f"- Name: {self._primary_user}",
            "",
            "## Email Accounts",
        ]

        if not self._email_accounts:
            lines.append("- None")
        else:
            for item in self._email_accounts:
                alias = item.get("alias", "unknown")
                email = item.get("email", "")
                provider = item.get("provider", "google")
                lines.append(f"- [{alias}] {email} ({provider})")

        lines.extend(["", "## Communication Handles"])
        if self._communication_handles:
            for platform, handle in self._communication_handles.items():
                lines.append(f"- {platform.capitalize()}: {handle}")
        else:
            lines.append("- None")

        lines.extend(["", "## Preferences"])
        for k, v in self._preferences.items():
            lines.append(f"- {k}: {v}")

        markdown_text = "\n".join(lines).strip() + "\n"

        os.makedirs(os.path.dirname(self.md_path), exist_ok=True)
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        # If initialized with a .json path, keep the json file synced so existing unit tests pass
        if hasattr(self, "raw_path") and self.raw_path.endswith(".json"):
            try:
                with open(self.raw_path, "w", encoding="utf-8") as f:
                    json.dump(self.get_accounts_data(), f, indent=2)
            except Exception:
                pass

    def get_accounts_data(self) -> Dict[str, Any]:
        """Returns structured account dictionary."""
        return {
            "primary_user": self._primary_user,
            "email_accounts": list(self._email_accounts),
            "communication_handles": dict(self._communication_handles),
            "preferences": dict(self._preferences),
        }

    def get_accounts_summary(self) -> str:
        """Formats the accounts into a clean context prompt block."""
        if os.path.isfile(self.md_path):
            try:
                with open(self.md_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    return content
            except Exception:
                pass

        lines = ["# User Accounts & Connected Context"]
        lines.append(f"- User: {self._primary_user}")
        if self._email_accounts:
            lines.append("- Email Accounts:")
            for email in self._email_accounts:
                alias = email.get("alias", "unknown")
                addr = email.get("email", "")
                provider = email.get("provider", "")
                lines.append(f"  * [{alias}] {addr} ({provider})")

        if self._communication_handles:
            lines.append("- Connected Channels:")
            for platform, handle in self._communication_handles.items():
                lines.append(f"  * {platform.capitalize()}: {handle}")

        if self._preferences:
            lines.append("- Personal Scopes:")
            for k, v in self._preferences.items():
                lines.append(f"  * {k}: {v}")

        return "\n".join(lines)

    def list_accounts(self) -> Dict[str, str]:
        """Returns mapping of account alias -> email address."""
        mapping: Dict[str, str] = {}
        for item in self._email_accounts:
            alias = item.get("alias", "").strip().lower()
            email = item.get("email", "").strip().lower()
            if alias and email:
                mapping[alias] = email
        return mapping

    def get_next_email_alias(self) -> str:
        """Finds next available arbitrary alias, e.g. email1, email2, email3..."""
        used_indices = set()
        for item in self._email_accounts:
            alias = item.get("alias", "").lower()
            m = re.match(r"^email(\d+)$", alias)
            if m:
                used_indices.add(int(m.group(1)))
        next_idx = 1
        while next_idx in used_indices:
            next_idx += 1
        return f"email{next_idx}"

    def resolve_expected_email(self, account: str) -> Optional[str]:
        """Resolves expected email for an alias, or returns the email if raw address passed."""
        clean = account.strip().lower()
        if "@" in clean:
            return clean

        mapping = self.list_accounts()
        if clean in mapping:
            return mapping[clean]

        if clean in ("default", "", "primary", "email1"):
            pref = self._preferences.get("preferred_email_alias", "email1")
            if pref in mapping:
                return mapping[pref]
            if "email1" in mapping:
                return mapping["email1"]
            if "primary" in mapping:
                return mapping["primary"]
            if mapping:
                return next(iter(mapping.values()))

        return None

    def resolve_alias_for_email(self, email: str) -> Optional[str]:
        """Finds configured alias matching an email address."""
        clean_email = email.strip().lower()
        for alias, addr in self.list_accounts().items():
            if addr.lower() == clean_email:
                return alias
        return None

    def update_account(
        self,
        alias: Optional[str] = None,
        email: str = "",
        provider: str = "google",
        scopes: Optional[List[str]] = None,
    ) -> str:
        """Upserts an email account alias in accounts.md. If alias is omitted or 'default', assigns next arbitrary alias (email1, email2...)."""
        clean_email = email.strip().lower()

        if not alias or alias.strip().lower() in ("default", ""):
            # If the only existing account is a placeholder, reuse its alias or email1
            if len(self._email_accounts) == 1 and self._email_accounts[0].get("email") in ("user1@example.com", "your_email@gmail.com"):
                clean_alias = self._email_accounts[0].get("alias", "email1")
            else:
                existing_alias = self.resolve_alias_for_email(clean_email)
                if existing_alias:
                    clean_alias = existing_alias
                else:
                    clean_alias = self.get_next_email_alias()
        else:
            clean_alias = alias.strip().lower()

        if not clean_email:
            self.delete_account(clean_alias)
            return clean_alias

        for item in self._email_accounts:
            if item.get("alias", "").lower() == clean_alias:
                item["email"] = clean_email
                item["provider"] = provider
                if scopes is not None:
                    item["scopes"] = scopes
                self.save()
                return clean_alias

        self._email_accounts.append({
            "alias": clean_alias,
            "email": clean_email,
            "provider": provider,
            "scopes": scopes or ["default"],
        })
        self.save()
        return clean_alias

    def delete_account(self, alias: str) -> bool:
        """Removes an account alias from accounts.md."""
        clean_alias = alias.strip().lower()
        original_len = len(self._email_accounts)
        self._email_accounts = [
            item for item in self._email_accounts
            if item.get("alias", "").lower() != clean_alias
        ]
        if len(self._email_accounts) < original_len:
            self.save()
            return True
        return False

    def update_handle(self, platform: str, handle: str) -> None:
        """Upserts a communication handle (telegram, discord, etc.)."""
        self._communication_handles[platform.lower().strip()] = handle.strip()
        self.save()

    def update_preference(self, key: str, value: str) -> None:
        """Upserts a personal preference or default scope."""
        self._preferences[key.strip()] = value.strip()
        self.save()

