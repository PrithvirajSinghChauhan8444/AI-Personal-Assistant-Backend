#!/usr/bin/env python3
"""
Assistant Browser Profile Launcher

Opens a dedicated, persistent browser window (Brave, Chrome, or Chromium) using the exact
assistant profile directory configured in `config/.env`.

Any logins, cookies, or sessions completed in this window are permanently saved on disk
and immediately available to the Me2 Assistant.
"""

import argparse
import os
import shutil
import subprocess
import sys


def try_load_dotenv() -> None:
    candidates = [".env", "config/.env", "../config/.env"]
    for path in candidates:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key not in os.environ:
                            os.environ[key] = val
            return


def resolve_browser(browser_type: str) -> tuple[str, str]:
    b_type = (browser_type or os.getenv("BROWSER_TYPE", "auto")).lower().strip()
    if not b_type:
        b_type = "auto"

    search_candidates = {
        "brave": [
            "brave",
            "brave-browser",
            "/usr/bin/brave",
            "/usr/bin/brave-browser",
            "/opt/brave.com/brave/brave-browser",
            "/snap/bin/brave",
        ],
        "chrome": [
            "google-chrome-stable",
            "google-chrome",
            "chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/opt/google/chrome/google-chrome",
        ],
        "chromium": [
            "chromium",
            "chromium-browser",
            "/usr/bin/chromium",
            "/usr/lib/chromium/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ],
    }

    def find_exe(candidates: list[str]) -> str | None:
        for cand in candidates:
            if "/" in cand:
                if os.path.isfile(cand) and os.access(cand, os.X_OK):
                    return cand
            else:
                found = shutil.which(cand)
                if found:
                    return found
        return None

    if b_type == "brave":
        return "brave", find_exe(search_candidates["brave"]) or "/usr/bin/brave"
    if b_type in ("chrome", "google-chrome"):
        return "chrome", find_exe(search_candidates["chrome"]) or "/usr/bin/google-chrome"
    if b_type == "chromium":
        return "chromium", find_exe(search_candidates["chromium"]) or "/usr/bin/chromium"

    for typ in ["brave", "chrome", "chromium"]:
        exe = find_exe(search_candidates[typ])
        if exe:
            return typ, exe

    return "chromium", "/usr/bin/chromium"


def resolve_user_data_dir(browser_type: str, profile_name: str | None, explicit_dir: str | None) -> str:
    if explicit_dir:
        return os.path.expanduser(explicit_dir)

    p_name = (profile_name or os.getenv("BROWSER_PROFILE_NAME", "assistant-profile")).strip()
    if not p_name:
        p_name = "assistant-profile"

    home = os.path.expanduser("~")
    return os.path.join(home, ".config", f"{browser_type}-{p_name}")


def main() -> None:
    try_load_dotenv()

    parser = argparse.ArgumentParser(
        description="Launch dedicated browser profile to log into accounts for Me2 Assistant."
    )
    parser.add_argument(
        "--browser",
        choices=["brave", "chrome", "chromium", "auto"],
        default=os.getenv("BROWSER_TYPE", "auto"),
        help="Browser to launch (brave, chrome, chromium, or auto).",
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("BROWSER_PROFILE_NAME", "assistant-profile"),
        help="Profile name (default: assistant-profile).",
    )
    parser.add_argument(
        "--url",
        default="about:blank",
        help="Initial URL to open (e.g. https://accounts.google.com).",
    )
    parser.add_argument(
        "--path",
        default=None,
        help="Override profile directory path directly.",
    )
    args = parser.parse_args()

    browser_type, exe_path = resolve_browser(args.browser)
    if os.getenv("BROWSER_EXECUTABLE_PATH") and not args.browser:
        exe_path = os.getenv("BROWSER_EXECUTABLE_PATH")

    explicit_dir = args.path or os.getenv("BROWSER_USER_DATA_DIR")
    profile_dir = resolve_user_data_dir(browser_type, args.profile, explicit_dir)

    os.makedirs(profile_dir, exist_ok=True)

    print("\n" + "=" * 70)
    print("🚀  Me2 Assistant — Dedicated Browser Profile Launcher")
    print("=" * 70)
    print(f"  • Browser:        {exe_path} ({browser_type})")
    print(f"  • Profile Name:   {args.profile}")
    print(f"  • User Data Dir:  {profile_dir}")
    print(f"  • Starting URL:   {args.url}")
    print("-" * 70)
    print("👉 INSTRUCTIONS:")
    print("   1. The browser window will open using the dedicated profile.")
    print("   2. Log into the accounts you want the assistant to access")
    print("      (e.g., Google Workspace, GitHub, internal dashboards).")
    print("   3. Once logged in, simply close the browser window.")
    print("   4. All cookies, tokens, and sessions will remain permanently")
    print("      saved in this directory for Me2 Assistant.")
    print("=" * 70 + "\n")

    cmd = [
        exe_path,
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if args.url and args.url != "about:blank":
        cmd.append(args.url)

    try:
        proc = subprocess.Popen(cmd)
        print("⏳ Waiting for browser to be closed...")
        proc.wait()
        print("\n✅ Browser profile updated! Sessions and logins are saved.\n")
    except KeyboardInterrupt:
        print("\n👋 Browser launcher closed.")
    except Exception as e:
        print(f"\n❌ Failed to launch browser: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
