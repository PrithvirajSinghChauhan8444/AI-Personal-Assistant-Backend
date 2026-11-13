#!/usr/bin/env python3
"""Google Workspace OAuth Authentication Utility.

Generates the Google OAuth consent URL, opens a local browser or prints the link,
and saves the exchanged OAuth2 tokens into config/token_<account>.json.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

# Canonical Google Workspace scopes matching assistant tool requirements
WORKSPACE_SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
]


def authenticate_account(
    account: str = "primary",
    config_dir: str = "config",
    port: int = 9915,
    open_browser: bool = True,
) -> Path:
    """Runs the OAuth2 authorization flow and persists tokens to config/token_<account>.json."""
    config_path = Path(config_dir).resolve()
    credentials_path = config_path / "credentials.json"

    if not credentials_path.is_file():
        print(f"❌ Error: credentials.json not found at {credentials_path}")
        print("Please download OAuth 2.0 Client ID (Desktop App) from Google Cloud Console.")
        sys.exit(1)

    account_key = account.strip().lower()
    if not account_key or account_key == "default":
        account_key = "primary"

    token_path = config_path / f"token_{account_key}.json"

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path),
        scopes=WORKSPACE_SCOPES,
    )

    print(f"\n🔐 Starting Google OAuth flow for account alias: '{account_key}'", flush=True)
    print(f"📁 Target token destination: {token_path}", flush=True)

    # Generate authorization URL
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    print("\n" + "=" * 80, flush=True)
    print("👉 AUTHORIZATION LINK:", flush=True)
    print(auth_url, flush=True)
    print("=" * 80 + "\n", flush=True)

    try:
        creds = flow.run_local_server(
            port=port,
            access_type="offline",
            prompt="consent",
            open_browser=open_browser,
        )
    except Exception as exc:
        fallback_port = 9260 if port != 9260 else 9916
        print(f"⚠️ Port {port} unavailable ({exc}). Retrying on port {fallback_port}...")
        creds = flow.run_local_server(
            port=fallback_port,
            access_type="offline",
            prompt="consent",
            open_browser=open_browser,
        )

    if not creds:
        print("❌ Authentication failed: no credentials received.")
        sys.exit(1)

    # Convert credentials to dictionary
    token_dict = json.loads(creds.to_json())
    if "token" in token_dict and "access_token" not in token_dict:
        token_dict["access_token"] = token_dict["token"]

    # Write formatted token JSON
    config_path.mkdir(parents=True, exist_ok=True)
    with open(token_path, "w", encoding="utf-8") as f:
        json.dump(token_dict, f, indent=2)
    os.chmod(token_path, 0o600)

    print(f"\n✅ Successfully authenticated Google account '{account_key}'!")
    print(f"💾 Token saved to: {token_path}")

    # If primary account, also synchronize to fallback token.json
    if account_key == "primary":
        fallback_path = config_path / "token.json"
        with open(fallback_path, "w", encoding="utf-8") as f:
            json.dump(token_dict, f, indent=2)
        os.chmod(fallback_path, 0o600)
        print(f"💾 Default fallback token also updated: {fallback_path}")

    return token_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Authenticate Google Workspace account for AI Personal Assistant")
    parser.add_argument(
        "--account",
        "-a",
        default="primary",
        help="Account alias (e.g. 'primary', 'college', 'personal'). Default: primary",
    )
    parser.add_argument(
        "--config-dir",
        "-c",
        default="config",
        help="Path to configuration directory containing credentials.json. Default: config",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=9915,
        help="Local redirect server port. Default: 9915",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not attempt to auto-launch system web browser (prints link only)",
    )

    args = parser.parse_args()
    authenticate_account(
        account=args.account,
        config_dir=args.config_dir,
        port=args.port,
        open_browser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
