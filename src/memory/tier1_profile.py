"""Tier 1 Core User Profile Manager (Backward-compatibility wrapper)."""

from src.memory.profiles.markdown_profile_parser import SectionBlock as _SectionBlock
from src.memory.profiles.user_profile import DEFAULT_CORE_PROFILE, UserProfileManager

__all__ = ["DEFAULT_CORE_PROFILE", "UserProfileManager", "_SectionBlock"]
