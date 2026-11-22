#!/usr/bin/env python3
"""Google Workspace OAuth Authentication Utility with Identity Verification.

Generates Google OAuth consent URL, opens local browser or prints direct link,
verifies that the logged-in email matches the expected account from accounts.md,
and saves the exchanged OAuth2 tokens into config/token_<account>.json.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import socket
import sys
import time
import urllib.request
import urllib.error
import wsgiref.simple_server
from pathlib import Path
from typing import Dict, Optional, Tuple

import psutil
from cryptography.fernet import Fernet
from google_auth_oauthlib.flow import InstalledAppFlow

# Relax oauthlib strict scope equality so auto-attached scopes (e.g. openid, incremental consent)
# do not abort token exchange.
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# Canonical Google Workspace scopes matching assistant tool requirements
WORKSPACE_SCOPES = [
    "openid",
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


def try_load_dotenv() -> None:
    """Loads environment variables from .env or config/.env if not already set, matching fernet.go."""
    for env_candidate in [Path(".env"), Path("config/.env")]:
        if env_candidate.is_file():
            try:
                for line in env_candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("\"'")
                    if key and key not in os.environ:
                        os.environ[key] = val
            except Exception as exc:
                print(f"⚠️ [Auth] Could not read {env_candidate}: {exc}", file=sys.stderr)


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


def get_authenticated_email(token: str, expected_client_id: Optional[str] = None) -> str:
    """Queries Google OAuth2 tokeninfo endpoint to retrieve and verify the actual authenticated email."""
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?access_token={token}"
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Personal-Assistant"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            aud = data.get("aud") or data.get("issued_to", "")
            if expected_client_id and aud and aud != expected_client_id:
                print(
                    f"⚠️ [Auth Security] Client ID mismatch! Token was issued for '{aud}', "
                    f"expected '{expected_client_id}'. Rejecting token.",
                    file=sys.stderr,
                )
                return ""
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


def get_derived_fernet_key() -> bytes:
    """Derives a 32-byte URL-safe base64 key matching Go's GetDerivedFernetKey()."""
    try_load_dotenv()
    key_str = os.getenv("TOKEN_ENCRYPTION_KEY")
    if not key_str:
        sys_pw = os.getenv("SYSTEM_PASSWORD") or os.getenv("AGENT_PASSWORD")
        if not sys_pw:
            print(
                "⚠️ [SECURITY WARNING] Neither TOKEN_ENCRYPTION_KEY, SYSTEM_PASSWORD, nor AGENT_PASSWORD is set.\n"
                "   Tokens will be encrypted with a known default secret. Set SYSTEM_PASSWORD or TOKEN_ENCRYPTION_KEY in .env!",
                file=sys.stderr,
                flush=True,
            )
            sys_pw = "default_secret_fallback_password"
        key_bytes = hashlib.sha256(sys_pw.encode("utf-8")).digest()
    else:
        key_bytes = hashlib.sha256(key_str.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(key_bytes)


def save_token(token_path: Path, token_dict: dict) -> None:
    """Encrypts token data using Fernet AES and writes with restricted 0o600 permissions."""
    token_path.parent.mkdir(parents=True, exist_ok=True)
    json_bytes = json.dumps(token_dict, indent=2).encode("utf-8")
    try:
        key = get_derived_fernet_key()
        fernet = Fernet(key)
        encrypted_bytes = fernet.encrypt(json_bytes)
        token_path.write_bytes(encrypted_bytes)
    except Exception as e:
        print(f"⚠️ Could not encrypt token ({e}), saving plaintext JSON with restricted permissions.", file=sys.stderr)
        token_path.write_bytes(json_bytes)

    os.chmod(token_path, 0o600)


def load_token(token_path: Path) -> Optional[dict]:
    """Loads and decrypts token file, supporting both plaintext JSON and Fernet encryption."""
    if not token_path.is_file():
        return None
    try:
        raw = token_path.read_bytes().strip()
        if not raw:
            return None
        if raw.startswith(b"{"):
            return json.loads(raw.decode("utf-8"))
        key = get_derived_fernet_key()
        fernet = Fernet(key)
        decrypted = fernet.decrypt(raw)
        return json.loads(decrypted.decode("utf-8"))
    except Exception as e:
        print(f"⚠️ Error reading token {token_path}: {e}", file=sys.stderr)
        return None


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Checks whether a TCP port can be bound on the local host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def terminate_stale_auth_process(target_account: str, port: Optional[int] = None) -> bool:
    """Terminates stale or orphaned auth_google.py processes.
    
    Safety guard: Only terminates processes running auth_google.py for the same target
    account or specific requested port. Never touches unrelated developer or system services.
    """
    current_pid = os.getpid()
    terminated_any = False

    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            if proc.pid == current_pid:
                continue
            cmdline = proc.info.get("cmdline") or []
            cmd_str = " ".join(cmdline)

            if "auth_google.py" not in cmd_str:
                continue

            matches_account = f"--account {target_account}" in cmd_str or f"-a {target_account}" in cmd_str
            matches_port = port is not None and (f"--port {port}" in cmd_str or f"-p {port}" in cmd_str)

            if matches_account or matches_port:
                print(f"🧹 Terminating stale Google auth process (PID {proc.pid}) to release port...", flush=True)
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except psutil.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1)
                terminated_any = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if terminated_any:
        time.sleep(0.3)
    return terminated_any


def find_available_port(
    preferred_port: int,
    target_account: str,
    max_search_range: int = 30,
    host: str = "127.0.0.1",
) -> int:
    """Finds an available local port starting from preferred_port.
    
    1. First clears any stale auth process for the target account or port.
    2. Tests if preferred_port is available.
    3. If busy, scans forward sequentially up to max_search_range to find the first open port.
    4. Falls back to OS-assigned ephemeral port (port 0) if all candidate ports are busy.
    """
    terminate_stale_auth_process(target_account=target_account, port=preferred_port)

    if is_port_available(preferred_port, host=host):
        return preferred_port

    print(f"⚠️ Port {preferred_port} in use or reserved. Searching for next available port...", flush=True)

    for candidate in range(preferred_port + 1, preferred_port + 1 + max_search_range):
        if is_port_available(candidate, host=host):
            print(f"✅ Found free local callback port: {candidate}", flush=True)
            return candidate

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        ephemeral = sock.getsockname()[1]
        print(f"✅ OS allocated ephemeral callback port: {ephemeral}", flush=True)
        return ephemeral


def get_preferred_alias(md_path: Optional[Path]) -> Optional[str]:
    """Reads preferred_email_alias from accounts.md if configured."""
    if not md_path or not md_path.is_file():
        return None
    try:
        content = md_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line.startswith(("- preferred_email_alias:", "* preferred_email_alias:")):
                parts = line.split(":", 1)
                if len(parts) == 2 and parts[1].strip():
                    return parts[1].strip().lower()
    except Exception:
        pass
    return None


def sanitize_filename(name: str) -> str:
    """Sanitizes an email or alias string for safe file storage matching Go's sanitizeFilename."""
    return re.sub(r"[^a-zA-Z0-9_\-\.\@]", "_", name)


def persist_account_credentials(
    config_path: Path,
    token_dict: dict,
    alias: str,
    email: Optional[str] = None,
    preferred_alias: Optional[str] = None,
    allow_default_fallback_update: bool = True,
) -> Path:
    """Saves encrypted credentials under alias and email with strict account isolation."""
    primary_token_path = config_path / f"token_{alias}.json"
    save_token(primary_token_path, token_dict)

    # Also save with email name if known so lookups by raw email succeed
    if email and "@" in email:
        email_token_path = config_path / f"token_{email}.json"
        save_token(email_token_path, token_dict)
        sanitized_email_path = config_path / f"token_{sanitize_filename(email)}.json"
        if sanitized_email_path != email_token_path:
            save_token(sanitized_email_path, token_dict)

    # Update default fallback token.json only if allowed (never on mismatch)
    fallback_path = config_path / "token.json"
    should_update_default = allow_default_fallback_update and (
        not fallback_path.exists() or (preferred_alias and alias == preferred_alias)
    )
    if should_update_default:
        save_token(fallback_path, token_dict)
        print(f"💾 Default fallback token also updated: {fallback_path}", flush=True)

    return primary_token_path


def authenticate_account(
    account: Optional[str] = None,
    config_dir: str = "config",
    port: int = 9915,
    open_browser: bool = True,
    max_attempts: int = 2,
) -> Path:
    """Runs OAuth2 authorization with multi-email verification against accounts.md."""
    config_path = Path(config_dir).resolve()
    credentials_path = config_path / "credentials.json"

    if not credentials_path.is_file():
        print(f"❌ Error: credentials.json not found at {credentials_path}")
        print("Please download OAuth 2.0 Client ID (Desktop App) from Google Cloud Console.")
        sys.exit(1)

    accounts_map, md_path = load_accounts_map()
    preferred_alias = get_preferred_alias(md_path)

    # Normalize input alias or email
    raw_input = (account or "").strip().lower()
    if raw_input in ("", "default", "auto", "any", "none"):
        raw_input = ""

    expected_email: Optional[str] = None
    target_alias: Optional[str] = None

    if raw_input:
        if "@" in raw_input:
            expected_email = raw_input
            # Check if this email is already mapped to an alias
            for al, em in accounts_map.items():
                if em.lower() == raw_input:
                    target_alias = al
                    break
            else:
                target_alias = raw_input.split("@")[0]
        else:
            target_alias = raw_input
            if target_alias in accounts_map:
                expected_email = accounts_map[target_alias]
            else:
                # User specified a new custom alias (e.g. 'work', 'college')
                expected_email = None
    else:
        # No account specified: dynamic discovery mode
        expected_email = None
        target_alias = preferred_alias or (next(iter(accounts_map.keys())) if accounts_map else None)

    active_alias_hint = target_alias or "auto"
    token_path = config_path / f"token_{active_alias_hint}.json"

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path),
        scopes=WORKSPACE_SCOPES,
    )

    attempts = 0
    prompt_option = "consent"

    # Allow socket address reuse so rapid retry loops don't get blocked by kernel TIME_WAIT
    wsgiref.simple_server.WSGIServer.allow_reuse_address = True

    while attempts < max_attempts:
        attempts += 1
        print(f"\n🔐 Starting Google OAuth flow for account alias: '{active_alias_hint}'", flush=True)
        if expected_email:
            print(f"🎯 Expected Email Address: {expected_email}", flush=True)
        print(f"📁 Target Token Destination: {token_path}", flush=True)

        # Dynamically discover an open port (cleaning any stale auth process for this account)
        active_port = find_available_port(preferred_port=port, target_account=active_alias_hint)
        flow.redirect_uri = f"http://localhost:{active_port}/"

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

        # Use xdg-open on Linux to avoid Python's webbrowser.Mozilla double-window bug
        browser_type = "xdg-open" if shutil.which("xdg-open") else None

        try:
            creds = flow.run_local_server(
                port=active_port,
                access_type="offline",
                prompt=prompt_option,
                open_browser=open_browser,
                browser=browser_type,
            )
        except Exception as exc:
            print(f"❌ OAuth callback server failed on port {active_port}: {exc}", file=sys.stderr)
            sys.exit(1)

        if not creds:
            print("❌ Authentication failed: no credentials received.", file=sys.stderr)
            sys.exit(1)

        token_dict = json.loads(creds.to_json())
        if "token" in token_dict and "access_token" not in token_dict:
            token_dict["access_token"] = token_dict["token"]

        actual_token = token_dict.get("access_token") or token_dict.get("token", "")
        client_id = flow.client_config.get("client_id")
        actual_email = get_authenticated_email(actual_token, expected_client_id=client_id)
        print(f"\n🔍 Authenticated Google Account: {actual_email or 'Unknown'}", flush=True)

        if not actual_email:
            print("❌ Authentication failed: could not verify email address from token.", file=sys.stderr)
            sys.exit(1)

        target_md = md_path or (Path.home() / ".config" / "ai-assistant" / "memory" / "accounts.md")

        # --- VERIFICATION STEP ---
        # Case 1: An explicit email was expected and matched
        if expected_email and actual_email.lower() == expected_email.lower():
            resolved_alias = target_alias or actual_email.split("@")[0]
            saved_path = persist_account_credentials(
                config_path=config_path,
                token_dict=token_dict,
                alias=resolved_alias,
                email=actual_email,
                preferred_alias=preferred_alias,
            )
            append_account_to_markdown(target_md, resolved_alias, actual_email)
            print(f"\n✅ Successfully authenticated Google account '{resolved_alias}' ({actual_email})!")
            print(f"💾 Token saved securely (Fernet encrypted) to: {saved_path}")
            return saved_path

        # Case 2: No specific expected email (Auto-detect mode or new custom alias)
        if not expected_email:
            known_alias = None
            for al, em in accounts_map.items():
                if em.lower() == actual_email.lower():
                    known_alias = al
                    break

            resolved_alias = target_alias or known_alias or actual_email.split("@")[0]
            saved_path = persist_account_credentials(
                config_path=config_path,
                token_dict=token_dict,
                alias=resolved_alias,
                email=actual_email,
                preferred_alias=preferred_alias,
            )
            append_account_to_markdown(target_md, resolved_alias, actual_email)
            print(f"\n✅ Successfully authenticated Google account '{resolved_alias}' ({actual_email})!")
            print(f"💾 Token saved securely (Fernet encrypted) to: {saved_path}")
            return saved_path

        # Case 3: Email MISMATCH (user logged into email A, but requested email B)
        print("\n" + "!" * 80, flush=True)
        print("⚠️  GOOGLE ACCOUNT MISMATCH DETECTED!", flush=True)
        print(f"   Target requested       : '{target_alias}' (Expected: {expected_email})", flush=True)
        print(f"   Actual account logged in: '{actual_email}'", flush=True)

        # Do NOT throw away valid credentials! Save them for the actual logged-in account,
        # but do not overwrite the default fallback token.json
        matched_alias = None
        for al, em in accounts_map.items():
            if em.lower() == actual_email.lower():
                matched_alias = al
                break

        fallback_alias = matched_alias or actual_email.split("@")[0]
        persist_account_credentials(
            config_path=config_path,
            token_dict=token_dict,
            alias=fallback_alias,
            email=actual_email,
            preferred_alias=preferred_alias,
            allow_default_fallback_update=False,
        )
        append_account_to_markdown(target_md, fallback_alias, actual_email)

        print(f"   💾 Saved valid credentials for: '{fallback_alias}' ({actual_email})", flush=True)
        print(f"   ⚠️ Expected account '{target_alias}' ({expected_email}) is STILL NOT authenticated!", flush=True)
        print("!" * 80 + "\n", flush=True)

        if attempts < max_attempts and open_browser:
            print(f"🔄 Re-launching browser with account chooser for '{target_alias}' ({expected_email}) (attempt {attempts+1}/{max_attempts})...", flush=True)
            prompt_option = "select_account"
            continue
        else:
            print(f"❌ Please log into {expected_email} to authorize account '{target_alias}'.", file=sys.stderr)
            sys.exit(1)

    print("❌ Maximum authentication attempts exceeded.", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Authenticate Google Workspace account for AI Personal Assistant")
    parser.add_argument(
        "--account",
        "-a",
        default="auto",
        help="Account alias (e.g. 'primary', 'college', 'work'), email address, or 'auto' to auto-detect. Default: auto",
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
