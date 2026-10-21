#!/usr/bin/env python3
"""
Launcher for AI Personal Assistant Telegram Remote Gateway.
Allows controlling the assistant remotely over Telegram with security whitelisting.
"""

import logging
import os
import sys
from dotenv import load_dotenv

# Ensure root directory is in sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

# Load environment configuration (.env)
load_dotenv()

BANNER = r"""
╭──────────────────────────────────────────────────────────╮
│  📱 Telegram Remote Gateway — AI Personal Assistant       │
│  Control your assistant remotely via Telegram            │
╰──────────────────────────────────────────────────────────╯
"""


def main():
    print(BANNER)

    # Configure logging
    logging.basicConfig(
        format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    raw_allowed_ids = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()

    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN is not configured in your environment or .env file.")
        print("\n📋 How to configure Telegram Remote Access:")
        print("  1. Open Telegram and search for @BotFather")
        print("  2. Send '/newbot' and follow instructions to get your Bot API Token")
        print("  3. Find your numeric Telegram User ID using @userinfobot on Telegram")
        print("  4. Add them to your .env file:")
        print("       TELEGRAM_BOT_TOKEN=your_token_here")
        print("       TELEGRAM_ALLOWED_USER_IDS=your_numeric_user_id\n")
        sys.exit(1)

    from modules.adapters.telegram.telegram_adapter import TelegramAdapter

    adapter = TelegramAdapter()

    allowed_ids = adapter.allowed_user_ids
    if not allowed_ids:
        print("⚠️ Warning: TELEGRAM_ALLOWED_USER_IDS is empty.")
        print("   For your security, unauthorized users will be blocked and shown their User ID.")
    else:
        print(f"🔒 Security Filter: {len(allowed_ids)} authorized User ID(s) configured.")

    print("🚀 Initializing Application Orchestrator and Telegram polling...\n")

    try:
        adapter.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 Stopping Telegram Gateway gracefully...")
        adapter.stop()
    except Exception as e:
        print(f"\n❌ Fatal Telegram Gateway Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
