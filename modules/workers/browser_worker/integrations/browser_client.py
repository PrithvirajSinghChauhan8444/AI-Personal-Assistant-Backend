import os
import sys
import math
import random
import asyncio
import threading
from typing import Dict, Any, List, Optional

class BackgroundPlaywrightRunner:
    """Dedicated background event loop runner for Playwright to ensure thread safety
    and persistence of browser pages across synchronous LangChain tool invocations.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = BackgroundPlaywrightRunner()
            return cls._instance

    def _run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=60)

runner = BackgroundPlaywrightRunner.get_instance()

def _find_browser_executable() -> Optional[str]:
    custom = os.getenv("BROWSER_EXECUTABLE_PATH", "").strip()
    if custom and os.path.exists(custom):
        return custom
    candidates = ["/usr/bin/brave", "/usr/bin/chromium", "/usr/bin/google-chrome"]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

async def _get_or_create_page():
    if runner.page is not None and not runner.page.is_closed():
        try:
            await runner.page.evaluate("1")
            return runner.page
        except Exception:
            pass

    from playwright.async_api import async_playwright
    import socket
    if runner.playwright is None:
        runner.playwright = await async_playwright().start()

    headless_env = os.getenv("BROWSER_HEADLESS", "False").lower()
    is_headless = headless_env in ("true", "1", "yes")
    exec_path = _find_browser_executable()

    # 1. Attempt to connect over CDP if port is open (attaches to running Brave with all active logins)
    cdp_url = os.getenv("BROWSER_CDP_URL", "http://localhost:9222").strip()
    if cdp_url:
        try:
            port = 9222
            if ":" in cdp_url:
                port = int(cdp_url.split(":")[-1].strip("/"))
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    runner.browser = await runner.playwright.chromium.connect_over_cdp(cdp_url)
                    runner.context = runner.browser.contexts[0] if runner.browser.contexts else await runner.browser.new_context()
                    runner.page = runner.context.pages[0] if runner.context.pages else await runner.context.new_page()
                    return runner.page
        except Exception:
            pass

    # 2. Launch persistent context with the user's real browser profile (access to saved passwords, cookies & logins)
    raw_user_data = os.getenv("BROWSER_USER_DATA_DIR", "~/.config/BraveSoftware/Brave-Browser").strip()
    user_data_path = os.path.expanduser(raw_user_data)
    profile_dir = "Default"
    if user_data_path.endswith("/Default"):
        user_data_path = os.path.dirname(user_data_path)
        profile_dir = "Default"

    launch_args = [
        f"--profile-directory={profile_dir}",
        "--disable-blink-features=AutomationControlled",
        "--no-first-run"
    ]

    try:
        runner.context = await runner.playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_path,
            executable_path=exec_path,
            headless=is_headless,
            viewport={"width": 1280, "height": 800},
            args=launch_args,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        runner.page = runner.context.pages[0] if runner.context.pages else await runner.context.new_page()
        return runner.page
    except Exception as lock_err:
        # If the main profile is locked by an already-running browser instance, fallback to dedicated persistent assistant profile
        fallback_dir = os.path.expanduser("~/.config/brave-assistant-profile")
        os.makedirs(fallback_dir, exist_ok=True)
        runner.context = await runner.playwright.chromium.launch_persistent_context(
            user_data_dir=fallback_dir,
            executable_path=exec_path,
            headless=is_headless,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled", "--no-first-run"],
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        runner.page = runner.context.pages[0] if runner.context.pages else await runner.context.new_page()
        return runner.page

DOM_MAP_JS = """
() => {
    function getRole(el) {
        const ariaRole = el.getAttribute('role');
        if (ariaRole) {
            if (['button', 'menuitem', 'tab', 'option'].includes(ariaRole)) return 'button';
            if (ariaRole === 'link') return 'link';
            if (ariaRole === 'checkbox') return 'checkbox';
            if (ariaRole === 'combobox' || ariaRole === 'listbox') return 'select';
            if (['textbox', 'searchbox', 'spinbutton'].includes(ariaRole)) return 'textbox';
        }
        const tag = el.tagName.toUpperCase();
        if (tag === 'BUTTON') return 'button';
        if (tag === 'A') return 'link';
        if (tag === 'SELECT') return 'select';
        if (tag === 'TEXTAREA') return 'textbox';
        if (tag === 'INPUT') {
            const t = (el.type || 'text').toLowerCase();
            if (t === 'checkbox') return 'checkbox';
            if (t === 'radio') return 'checkbox';
            if (['submit', 'button', 'reset', 'image'].includes(t)) return 'button';
            return 'textbox';
        }
        return 'other';
    }

    function getLabel(el) {
        let text = (el.innerText || '').trim();
        if (!text) text = (el.getAttribute('aria-label') || '').trim();
        if (!text) text = (el.placeholder || '').trim();
        if (!text) text = (el.title || '').trim();
        if (!text) text = (el.getAttribute('name') || '').trim();
        if (!text) text = (el.value || '').trim();
        if (text.length > 80) text = text.substring(0, 77) + '...';
        return text;
    }

    const allElements = document.getElementsByTagName('*');
    const candidates = [];

    for (let i = 0; i < allElements.length; i++) {
        const el = allElements[i];
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) continue;
        if (rect.left >= window.innerWidth || rect.right <= 0 || rect.top >= window.innerHeight || rect.bottom <= 0) continue;

        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) continue;

        const tag = el.tagName.toUpperCase();
        const isStandard = ['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(tag);
        const ariaRole = el.getAttribute('role') || '';
        const hasInteractiveRole = ['button', 'link', 'checkbox', 'radio', 'tab', 'option', 'menuitem', 'textbox', 'searchbox'].includes(ariaRole);
        const hasClickAttr = el.hasAttribute('onclick') || el.getAttribute('tabindex') === '0';
        const hasPointer = style.cursor === 'pointer';

        if (isStandard || hasInteractiveRole || hasClickAttr || hasPointer) {
            candidates.push({ el, rect });
        }
    }

    let idCounter = 1;
    const result = [];
    candidates.forEach(({ el, rect }) => {
        let ancestor = el.parentElement;
        while (ancestor) {
            const aTag = ancestor.tagName.toUpperCase();
            if (['BUTTON', 'A'].includes(aTag) && candidates.some(c => c.el === ancestor)) {
                return;
            }
            ancestor = ancestor.parentElement;
        }

        const label = getLabel(el);
        const tag = el.tagName.toUpperCase();
        if (!label && !['INPUT', 'SELECT', 'TEXTAREA'].includes(tag)) return;

        el.setAttribute('data-agent-id', idCounter.toString());
        result.push({
            id: idCounter++,
            tag: el.tagName.toLowerCase(),
            role: getRole(el),
            label: label
        });
    });

    return result;
}
"""

async def _navigate_coro(url: str) -> str:
    page = await _get_or_create_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(1.5)
    elements = await page.evaluate(DOM_MAP_JS)
    out = [f"Successfully navigated to {url}. Title: '{await page.title()}'", "\nInteractive Elements on screen:"]
    for el in elements[:35]:
        out.append(f"[{el['id']}] {el['role']} \"{el['label']}\"")
    return "\n".join(out)

async def _get_active_page():
    if runner.context and runner.context.pages:
        for p in reversed(runner.context.pages):
            if not p.is_closed():
                runner.page = p
                return p
    return await _get_or_create_page()

async def _click_coro(index_or_selector: Any) -> str:
    page = await _get_active_page()
    target_sel = f"[data-agent-id='{index_or_selector}']" if str(index_or_selector).isdigit() else str(index_or_selector)
    try:
        await page.wait_for_selector(target_sel, timeout=7000)
        await page.click(target_sel)
        await asyncio.sleep(2.0)
        # Check if a new tab was opened
        page = await _get_active_page()
        elements = await page.evaluate(DOM_MAP_JS)
        out = [f"Clicked element {index_or_selector}. Active URL: {page.url} (Title: '{await page.title()}')", "Updated Interactive Elements:"]
        for el in elements[:30]:
            out.append(f"[{el['id']}] {el['role']} \"{el['label']}\"")
        return "\n".join(out)
    except Exception as e:
        return f"Failed to click element {index_or_selector}: {e}"

async def _type_coro(index_or_selector: Any, text: str, press_enter: bool = False) -> str:
    page = await _get_active_page()
    target_sel = f"[data-agent-id='{index_or_selector}']" if str(index_or_selector).isdigit() else str(index_or_selector)
    try:
        await page.wait_for_selector(target_sel, timeout=7000)
        await page.click(target_sel)
        await page.fill(target_sel, "")
        await page.type(target_sel, text, delay=50)
        if press_enter:
            await page.keyboard.press("Enter")
            await asyncio.sleep(2.5)
            page = await _get_active_page()
            elements = await page.evaluate(DOM_MAP_JS)
            out = [f"Typed '{text}' and submitted Enter. Active URL: {page.url}", "Updated Interactive Elements:"]
            for el in elements[:30]:
                out.append(f"[{el['id']}] {el['role']} \"{el['label']}\"")
            return "\n".join(out)
        return f"Typed '{text}' into element {index_or_selector}."
    except Exception as e:
        return f"Failed to type into element {index_or_selector}: {e}"

async def _scroll_coro(direction: str = "down", amount: int = 500) -> str:
    page = await _get_or_create_page()
    sign = 1 if direction == "down" else -1
    await page.evaluate(f"window.scrollBy(0, {sign * abs(amount)})")
    await asyncio.sleep(0.5)
    return f"Scrolled page {direction} by {amount} pixels."

async def _screenshot_coro(filename: Optional[str] = None) -> str:
    page = await _get_or_create_page()
    os.makedirs("Memory/screenshots", exist_ok=True)
    file_path = filename or f"Memory/screenshots/shot_{int(asyncio.get_event_loop().time())}.png"
    await page.screenshot(path=file_path)
    return f"Screenshot captured and saved to {file_path}."

async def _read_content_coro(max_chars: int = 4000) -> str:
    page = await _get_or_create_page()
    text = await page.evaluate("() => document.body.innerText")
    trimmed = text[:max_chars] if text else "No visible text content found."
    return f"Page Content ({page.url}):\n{trimmed}"

async def _dom_map_coro() -> str:
    page = await _get_or_create_page()
    elements = await page.evaluate(DOM_MAP_JS)
    out = ["Interactive Elements on screen:"]
    for el in elements[:40]:
        out.append(f"[{el['id']}] {el['role']} \"{el['label']}\"")
    return "\n".join(out)

async def _close_browser_coro() -> str:
    if runner.browser:
        await runner.browser.close()
        runner.browser = None
        runner.page = None
    return "Browser session closed."

# Synchronous public API wrappers called by LangChain tools
def navigate_to_url(url: str) -> str:
    return runner.run(_navigate_coro(url))

def click_element(index_or_selector: Any) -> str:
    return runner.run(_click_coro(index_or_selector))

def type_text(index_or_selector: Any, text: str, press_enter: bool = False) -> str:
    return runner.run(_type_coro(index_or_selector, text, press_enter=press_enter))

def scroll_page(direction: str = "down", amount: int = 500) -> str:
    return runner.run(_scroll_coro(direction=direction, amount=amount))

def take_screenshot(file_path: Optional[str] = None) -> str:
    return runner.run(_screenshot_coro(file_path))

def get_page_content(max_chars: int = 4000) -> str:
    return runner.run(_read_content_coro(max_chars=max_chars))

def get_dom_map() -> str:
    return runner.run(_dom_map_coro())

def close_browser() -> str:
    return runner.run(_close_browser_coro())
