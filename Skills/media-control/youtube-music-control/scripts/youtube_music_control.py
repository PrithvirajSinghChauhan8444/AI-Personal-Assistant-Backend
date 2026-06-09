#!/usr/bin/env python3
import os
import sys
import argparse
import asyncio
import json
from dotenv import load_dotenv

# Find project root and load environment variables
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
load_dotenv(os.path.join(project_root, ".env"), override=True)

async def get_browser_and_page(playwright):
    cdp_url = os.getenv("BROWSER_CDP_URL", "")
    browser_type_str = os.getenv("BROWSER_TYPE", "chromium").lower()
    if browser_type_str not in ["chromium", "firefox", "webkit"]:
        browser_type_str = "chromium"
        
    browser_launcher = getattr(playwright, browser_type_str)
    
    # Try CDP connection first
    if cdp_url:
        try:
            print(f"🌐 [YTM Control] Connecting over CDP to {cdp_url}...", file=sys.stderr)
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            return browser, context, True
        except Exception as e:
            print(f"⚠️ CDP connection failed: {e}. Falling back to launching browser.", file=sys.stderr)
            
    # Launch persistent context
    user_data_dir = os.getenv("BROWSER_USER_DATA_DIR", "")
    executable_path = os.getenv("BROWSER_EXECUTABLE_PATH", "")
    headless_mode = os.getenv("BROWSER_HEADLESS", "True").lower() == "true"
    slow_mo_ms = int(os.getenv("BROWSER_SLOW_MO", "0"))
    
    launch_kwargs = {
        "headless": headless_mode,
        "slow_mo": slow_mo_ms,
    }
    if executable_path:
        launch_kwargs["executable_path"] = os.path.expanduser(executable_path)
    if browser_type_str == "chromium":
        launch_kwargs["args"] = ["--password-store=basic"]
        
    if user_data_dir:
        user_data_dir = os.path.expanduser(user_data_dir)
        # Check profile folder
        profile_directory = None
        if browser_type_str == "chromium":
            basename = os.path.basename(user_data_dir)
            if basename == "Default" or basename.startswith("Profile "):
                profile_directory = basename
                user_data_dir = os.path.dirname(user_data_dir)
                
        launch_args = launch_kwargs.get("args", [])
        if profile_directory:
            launch_args.append(f"--profile-directory={profile_directory}")
            
        print(f"🌐 [YTM Control] Launching persistent browser context at {user_data_dir}...", file=sys.stderr)
        try:
            context = await browser_launcher.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless_mode,
                slow_mo=slow_mo_ms,
                executable_path=launch_kwargs.get("executable_path"),
                args=launch_args
            )
            return None, context, False
        except Exception as e:
            print(f"⚠️ Persistent launch failed (possibly browser is already running): {e}", file=sys.stderr)
            print("Trying to launch a standard temporary profile context instead...", file=sys.stderr)
            
    # Fallback to standard launch
    print(f"🌐 [YTM Control] Launching temporary browser instance...", file=sys.stderr)
    browser = await browser_launcher.launch(
        headless=headless_mode,
        slow_mo=slow_mo_ms,
        executable_path=launch_kwargs.get("executable_path"),
        args=launch_kwargs.get("args", [])
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" if browser_type_str == "chromium" else None
    )
    return browser, context, False

async def find_ytmusic_page(context):
    for page in context.pages:
        if "music.youtube.com" in page.url:
            return page
    return None

async def main():
    parser = argparse.ArgumentParser(description="YouTube Music Playback Browser Controller")
    parser.add_argument("action", choices=["play", "pause", "toggle", "next", "prev", "status", "search"], help="Action to perform")
    parser.add_argument("--query", "-q", help="Search query (only used with 'search')")
    args = parser.parse_args()

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser, context, is_cdp = await get_browser_and_page(p)
        
        try:
            page = await find_ytmusic_page(context)
            
            # If YouTube Music is not open and we want to control playback, we can't
            if not page:
                if args.action in ["status", "pause", "toggle", "next", "prev"]:
                    print(json.dumps({"error": "YouTube Music is not open in any browser tab."}))
                    return
                # For play/search, we open it
                print("🎵 YouTube Music is not open. Opening a new tab...", file=sys.stderr)
                page = await context.new_page()
                await page.goto("https://music.youtube.com", wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
            
            # Execute action
            if args.action == "status":
                status_data = await page.evaluate("""() => {
                    const titleEl = document.querySelector('ytmusic-player-bar .title');
                    const bylineEl = document.querySelector('ytmusic-player-bar .byline');
                    const playPauseBtn = document.querySelector('ytmusic-player-bar #play-pause-button');
                    const timeInfoEl = document.querySelector('ytmusic-player-bar .time-info');
                    
                    return {
                        title: titleEl ? titleEl.innerText : 'Unknown Title',
                        artist: bylineEl ? bylineEl.innerText : 'Unknown Artist',
                        status: playPauseBtn ? (playPauseBtn.getAttribute('title') === 'Pause' ? 'Playing' : 'Paused') : 'Unknown Status',
                        time: timeInfoEl ? timeInfoEl.innerText : '0:00 / 0:00'
                    };
                }""")
                print(json.dumps(status_data))
                
            elif args.action == "play":
                await page.evaluate("""() => {
                    const playBtn = document.querySelector('ytmusic-player-bar #play-pause-button[title="Play"]');
                    if (playBtn) {
                        playBtn.click();
                    } else {
                        // Fallback: click play-pause-button directly if we can't determine state
                        const btn = document.querySelector('ytmusic-player-bar #play-pause-button');
                        if (btn) btn.click();
                    }
                }""")
                print(json.dumps({"status": "command_sent", "action": "play"}))
                
            elif args.action == "pause":
                await page.evaluate("""() => {
                    const pauseBtn = document.querySelector('ytmusic-player-bar #play-pause-button[title="Pause"]');
                    if (pauseBtn) {
                        pauseBtn.click();
                    } else {
                        // Fallback: click play-pause-button directly if we can't determine state
                        const btn = document.querySelector('ytmusic-player-bar #play-pause-button');
                        if (btn) btn.click();
                    }
                }""")
                print(json.dumps({"status": "command_sent", "action": "pause"}))
                
            elif args.action == "toggle":
                await page.evaluate("""() => {
                    const btn = document.querySelector('ytmusic-player-bar #play-pause-button');
                    if (btn) btn.click();
                }""")
                print(json.dumps({"status": "command_sent", "action": "toggle"}))
                
            elif args.action == "next":
                await page.evaluate("""() => {
                    const btn = document.querySelector('ytmusic-player-bar .next-button');
                    if (btn) btn.click();
                }""")
                print(json.dumps({"status": "command_sent", "action": "next"}))
                
            elif args.action == "prev":
                await page.evaluate("""() => {
                    const btn = document.querySelector('ytmusic-player-bar .previous-button');
                    if (btn) btn.click();
                }""")
                print(json.dumps({"status": "command_sent", "action": "prev"}))
                
            elif args.action == "search":
                if not args.query:
                    print(json.dumps({"error": "Search query is required for search action. Use --query."}))
                    return
                
                print(f"🔍 Searching YouTube Music for: {args.query}", file=sys.stderr)
                # Wait for search box or click it
                try:
                    await page.click("ytmusic-search-box input", timeout=5000)
                except Exception:
                    # Fallback click on any search indicator
                    await page.click("ytmusic-search-box", timeout=5000)
                
                await page.fill("ytmusic-search-box input", args.query)
                await page.press("ytmusic-search-box input", "Enter")
                
                # Wait for search results
                await page.wait_for_timeout(3000)
                
                # Play first result
                success = await page.evaluate("""() => {
                    const firstPlayBtn = document.querySelector('ytmusic-responsive-list-item-renderer ytmusic-play-button-renderer');
                    if (firstPlayBtn) {
                        firstPlayBtn.click();
                        return true;
                    }
                    const firstLink = document.querySelector('ytmusic-responsive-list-item-renderer a');
                    if (firstLink) {
                        firstLink.click();
                        return true;
                    }
                    return false;
                }""")
                
                if success:
                    print(json.dumps({"status": "searching_and_playing", "query": args.query}))
                else:
                    print(json.dumps({"error": "Failed to find or click the first search result."}))
                    
            # Keep browser open if it's CDP, otherwise save page changes
            if not is_cdp:
                await page.wait_for_timeout(2000)
                
        finally:
            if browser and not is_cdp:
                await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
