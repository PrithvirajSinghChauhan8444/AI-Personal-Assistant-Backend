"""Tier 2 Connected Accounts Context Manager (Backward-compatibility wrapper)."""

from src.memory.profiles.connected_accounts import (
    DEFAULT_ACCOUNTS_MD,
    AccountsContextManager,
)

__all__ = ["DEFAULT_ACCOUNTS_MD", "AccountsContextManager"]
