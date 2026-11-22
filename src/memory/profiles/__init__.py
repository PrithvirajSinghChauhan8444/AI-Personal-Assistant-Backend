"""Profiles subsystem for user core profile and connected accounts."""

from src.memory.profiles.atomic_file import atomic_write_text
from src.memory.profiles.connected_accounts import AccountsContextManager
from src.memory.profiles.markdown_profile_parser import SectionBlock
from src.memory.profiles.user_profile import DEFAULT_CORE_PROFILE, UserProfileManager

__all__ = [
    "atomic_write_text",
    "AccountsContextManager",
    "DEFAULT_CORE_PROFILE",
    "SectionBlock",
    "UserProfileManager",
]
