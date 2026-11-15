#!/usr/bin/env python3
"""Google Workspace OAuth Authentication Utility with Identity Verification.

Generates Google OAuth consent URL, opens local browser or prints direct link,
verifies that the logged-in email matches the expected account from accounts.md,
and saves the exchanged OAuth2 tokens into config/token_<account>.json.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Optional, Tuple

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
    "https://www.googleapis.com/auth/userinfo.email",
]


def _find_accounts_markdown() -> Optional[Path]:
    """Finds the accounts.md file in standard assistant memory locations."""
    candidates = []

    # 1. AI_ASSISTANT_MEMORY_DIR environment variable
    if os.environ.get("AI_ASSISTANT_MEMORY_DIR"):
        candidates.append(Path(os.environ["AI_ASSISTANT_MEMORY_DIR"]) / "accounts.md")

    # 2. system.json in config or not_comit
    for sys_json in ["config/system.json", "not_comit/system.json", "system.json"]:
        p = Path(sys_json)
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("memory_dir"):
                    candidates.append(Path(data["memory_dir"]) / "accounts.md")
                if data.get("workspace_dir"):
                    candidates.append(Path(data["workspace_dir"]) / "Memory" / "accounts.md")
            except Exception:
                pass

    # 3. Standard user home and workspace paths
    home = Path.home()
    candidates.extend([
        home / ".config" / "ai-assistant" / "memory" / "accounts.md",
        Path("workspace/Memory/accounts.md"),
        Path("Memory/accounts.md"),
        Path("config/accounts.md"),
    ])

    for c in candidates:
        if c.is_file():
            return c.resolve()

    return None


def load_accounts_map() -> Tuple[Dict[str, str], Optional[Path]]:
    """Loads alias -> email mappings from accounts.md (falling back to legacy json if needed)."""
    mapping: Dict[str, str] = {}
    md_path = _find_accounts_markdown()

    if md_path and md_path.is_file():
        try:
            content = md_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if not (line.startswith("- ") or line.startswith("* ")):
                    continue
                item = line[2:].strip()
                # Pattern: - [alias] email@domain (provider)
                m = re.match(r"^\[([a-zA-Z0-9_\-\.]+)\]\s*([^\s\(]+)", item)
                if m:
                    alias = m.group(1).strip().lower()
                    email = m.group(2).strip().lower()
                    if "@" in email:
                        mapping[alias] = email
                elif ":" in item:
                    k, v = item.split(":", 1)
                    alias = k.strip().lower()
                    email = v.strip().lower()
                    if "@" in email:
                        mapping[alias] = email
            if mapping:
                return mapping, md_path
        except Exception as e:
            print(f"⚠️ [Auth] Warning reading {md_path}: {e}")

    # Fallback to config/google_accounts.json or accounts.json
    for fb in ["config/google_accounts.json", "config/accounts.json"]:
        p = Path(fb)
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if "email_accounts" in data:
                        for item in data["email_accounts"]:
                            if item.get("alias") and item.get("email"):
                                mapping[item["alias"].lower()] = item["email"].lower()
                    else:
                        for k, v in data.items():
                            if isinstance(v, str) and "@" in v:
                                mapping[k.lower()] = v.lower()
                    return mapping, None
            except Exception:
                pass

    return mapping, md_path


def get_authenticated_email(token: str) -> str:
    """Queries Google OAuth2 tokeninfo endpoint to retrieve the actual authenticated email."""
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?access_token={token}"
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Personal-Assistant"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            email = data.get("email", "").strip().lower()
            if email:
                return email
    except Exception as e:
        print(f"⚠️ [Auth] Tokeninfo email check returned: {e}")

    # Fallback to userinfo endpoint
    try:
        url = "https://www.googleapis.com/oauth2/v2/userinfo"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "AI-Personal-Assistant",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("email", "").strip().lower()
    except Exception as e:
        print(f"⚠️ [Auth] Userinfo email check returned: {e}")

    return ""


def append_account_to_markdown(md_path: Path, alias: str, email: str) -> None:
    """Appends or updates a verified account in accounts.md."""
    try:
        if not md_path.is_file():
            md_path.parent.mkdir(parents=True, exist_ok=True)
            content = f"# User Accounts & Connected Context\n\n## Email Accounts\n- [{alias}] {email} (google)\n"
            md_path.write_text(content, encoding="utf-8")
            return

        content = md_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        new_lines = []
        updated = False

        for line in lines:
            if re.match(rf"^\s*[\-\*]\s*\[{re.escape(alias)}\]", line, re.IGNORECASE):
                new_lines.append(f"- [{alias}] {email} (google)")
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            # Find ## Email Accounts section
            inserted = False
            final_lines = []
            for i, line in enumerate(new_lines):
                final_lines.append(line)
                if line.strip().lower() == "## email accounts":
                    final_lines.append(f"- [{alias}] {email} (google)")
                    inserted = True

            if not inserted:
                final_lines.extend(["", "## Email Accounts", f"- [{alias}] {email} (google)"])
            new_lines = final_lines

        md_path.write_text("\n".join(new_lines).strip() + "\n", encoding="utf-8")
        print(f"📝 Recorded account alias '[{alias}] -> {email}' in {md_path}")
    except Exception as e:
        print(f"⚠️ Could not update accounts.md: {e}")


def authenticate_account(
    account: str = "email1",
    config_dir: str = "config",
    port: int = 9915,
    open_browser: bool = True,
    max_attempts: int = 2,
) -> Path:
    """Runs OAuth2 authorization with email verification against accounts.md."""
    config_path = Path(config_dir).resolve()
    credentials_path = config_path / "credentials.json"

    if not credentials_path.is_file():
        print(f"❌ Error: credentials.json not found at {credentials_path}")
        print("Please download OAuth 2.0 Client ID (Desktop App) from Google Cloud Console.")
        sys.exit(1)

    accounts_map, md_path = load_accounts_map()

    # Determine target alias and expected email
    raw_account = account.strip().lower()
    expected_email: Optional[str] = None
    account_key = "email1"

    if "@" in raw_account:
        expected_email = raw_account
        # Check if known alias matches this email
        for alias, em in accounts_map.items():
            if em.lower() == raw_account:
                account_key = alias
                break
        else:
            # Auto-assign next arbitrary alias if not mapped
            account_key = raw_account.split("@")[0]
    else:
        if not raw_account or raw_account == "default":
            account_key = "email1"
            if "email1" not in accounts_map and "primary" in accounts_map:
                account_key = "primary"
        else:
            account_key = raw_account
        expected_email = accounts_map.get(account_key)

    token_path = config_path / f"token_{account_key}.json"

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path),
        scopes=WORKSPACE_SCOPES,
    )

    attempts = 0
    prompt_option = "consent"

    while attempts < max_attempts:
        attempts += 1
        print(f"\n🔐 Starting Google OAuth flow for account alias: '{account_key}'", flush=True)
        if expected_email:
            print(f"🎯 Expected Email Address: {expected_email}", flush=True)
        print(f"📁 Target Token Destination: {token_path}", flush=True)

        # Generate authorization URL
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt=prompt_option,
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
                prompt=prompt_option,
                open_browser=open_browser,
            )
        except Exception as exc:
            fallback_port = 9260 if port != 9260 else 9916
            print(f"⚠️ Port {port} unavailable ({exc}). Retrying on port {fallback_port}...")
            creds = flow.run_local_server(
                port=fallback_port,
                access_type="offline",
                prompt=prompt_option,
                open_browser=open_browser,
            )

        if not creds:
            print("❌ Authentication failed: no credentials received.")
            sys.exit(1)

        token_dict = json.loads(creds.to_json())
        if "token" in token_dict and "access_token" not in token_dict:
            token_dict["access_token"] = token_dict["token"]

        actual_token = token_dict.get("access_token") or token_dict.get("token", "")
        actual_email = get_authenticated_email(actual_token)
        print(f"\n🔍 Authenticated Google Account: {actual_email or 'Unknown'}", flush=True)

        # --- VERIFICATION STEP ---
        # Did the user log into the correct account?
        if not expected_email or (actual_email and actual_email.lower() == expected_email.lower()):
            # Verification SUCCESS: User logged into the expected account
            config_path.mkdir(parents=True, exist_ok=True)
            with open(token_path, "w", encoding="utf-8") as f:
                json.dump(token_dict, f, indent=2)
            os.chmod(token_path, 0o600)

            print(f"\n✅ Successfully authenticated Google account '{account_key}' ({actual_email})!")
            print(f"💾 Token saved to: {token_path}")

            if account_key == "primary":
                fallback_path = config_path / "token.json"
                with open(fallback_path, "w", encoding="utf-8") as f:
                    json.dump(token_dict, f, indent=2)
                os.chmod(fallback_path, 0o600)
                print(f"💾 Default fallback token also updated: {fallback_path}")

            # Record or update in accounts.md if path is known
            if actual_email:
                target_md = md_path or (Path.home() / ".config" / "ai-assistant" / "memory" / "accounts.md")
                append_account_to_markdown(target_md, account_key, actual_email)

            return token_path

        # --- MISMATCH DETECTED: THE USER HAS DONE WRONG ---
        # The user clicked the wrong Google account in their browser
        print("\n" + "!" * 80, flush=True)
        print("⚠️  GOOGLE ACCOUNT MISMATCH DETECTED!", flush=True)
        print(f"   Target alias requested : '{account_key}' (Expected: {expected_email})", flush=True)
        print(f"   Actual account logged in: '{actual_email}'", flush=True)

        # Check if actual_email matches another configured account
        matched_alias = None
        for alias, em in accounts_map.items():
            if em.lower() == actual_email.lower():
                matched_alias = alias
                break

        if matched_alias:
            # Preserve the valid login for the matched account!
            matched_token_path = config_path / f"token_{matched_alias}.json"
            with open(matched_token_path, "w", encoding="utf-8") as f:
                json.dump(token_dict, f, indent=2)
            os.chmod(matched_token_path, 0o600)
            print(f"   💾 Saved valid credentials to matching account: {matched_token_path}", flush=True)
            print(f"   ❌ Account '{account_key}' is STILL NOT authenticated!", flush=True)
        else:
            print(f"   ❌ Rejected credentials for '{account_key}' to prevent account pollution.", flush=True)

        print("!" * 80 + "\n", flush=True)

        if attempts < max_attempts and open_browser:
            print(f"🔄 Re-launching browser with account chooser for '{account_key}' (attempt {attempts+1}/{max_attempts})...", flush=True)
            prompt_option = "select_account"
            continue
        else:
            print(f"❌ Authentication aborted: Please log into {expected_email} to authorize account '{account_key}'.", file=sys.stderr)
            sys.exit(1)

    print("❌ Maximum authentication attempts exceeded.", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Authenticate Google Workspace account for AI Personal Assistant")
    parser.add_argument(
        "--account",
        "-a",
        default="email1",
        help="Account alias (e.g. 'email1', 'email2', etc.) or email address. Default: email1",
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
