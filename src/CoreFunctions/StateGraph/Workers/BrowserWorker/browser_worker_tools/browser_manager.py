import asyncio
import os
import random
import math
import socket
import subprocess
from dotenv import load_dotenv

_playwright_ctx = None
_browser = None
_browser_context = None
_page = None

async def _apply_stealth_scripts(context):
    stealth_js = """
    () => {
        try {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        } catch (e) {}

        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };

        try {
            const mockPlugins = [
                { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }
            ];
            Object.defineProperty(navigator, 'plugins', {
                get: () => mockPlugins
            });
        } catch (e) {}

        try {
            const originalQuery = navigator.permissions.query;
            navigator.permissions.query = (parameters) => 
                parameters.name === 'notifications' ? 
                    Promise.resolve({ state: Notification.permission }) : 
                    originalQuery(parameters);
        } catch (e) {}

        try {
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel(R) Iris(R) Xe Graphics';
                }
                return getParameter.call(this, parameter);
            };
        } catch (e) {}
    }
    """
    await context.add_init_script(stealth_js)

async def _human_click(page, selector):
    element = await page.wait_for_selector(selector, timeout=10000)
    box = await element.bounding_box()
    if not box:
        await page.click(selector, timeout=10000)
        return
        
    target_x = box['x'] + box['width'] * random.uniform(0.2, 0.8)
    target_y = box['y'] + box['height'] * random.uniform(0.2, 0.8)
    
    start_x = random.randint(0, 1024)
    start_y = random.randint(0, 768)
    
    steps = 10
    for i in range(steps + 1):
        t = i / steps
        mid_x = (start_x + target_x) / 2
        mid_y = (start_y + target_y) / 2
        control_x = mid_x + random.uniform(-100, 100)
        control_y = mid_y + random.uniform(-100, 100)
        
        x = (1 - t)**2 * start_x + 2 * (1 - t) * t * control_x + t**2 * target_x
        y = (1 - t)**2 * start_y + 2 * (1 - t) * t * control_y + t**2 * target_y
        
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.01, 0.03))
        
    await asyncio.sleep(random.uniform(0.1, 0.3))
    
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.05, 0.15))
    await page.mouse.up()

async def _human_type(page, selector, text):
    element = await page.wait_for_selector(selector, timeout=10000)
    await element.click()
    
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await asyncio.sleep(random.uniform(0.1, 0.2))
    
    for char in text:
        if random.random() < 0.03 and char.isalnum():
            wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
            await page.keyboard.type(wrong_char)
            await asyncio.sleep(random.uniform(0.1, 0.25))
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.15, 0.3))
            
        await page.keyboard.type(char)
        if char in ".,!?":
            delay = random.uniform(0.3, 0.6)
        elif char == " ":
            delay = random.uniform(0.15, 0.3)
        else:
            delay = random.uniform(0.05, 0.15)
        await asyncio.sleep(delay)

async def _human_scroll(page, direction="down", distance=300):
    sign = 1 if direction == "down" else -1
    steps = 15
    for i in range(steps + 1):
        t = i / steps
        multiplier = 0.5 * (1 - math.cos(t * math.pi))
        await page.evaluate(f"window.scrollBy(0, {distance / steps * sign})")
        await asyncio.sleep(random.uniform(0.015, 0.03))

async def _get_browser_page():
    global _playwright_ctx, _browser, _browser_context, _page
    if _page is None or _page.is_closed():
        from playwright.async_api import async_playwright
        
        # Look for .env in root directory
        curr = os.path.abspath(__file__)
        while curr and not os.path.exists(os.path.join(curr, "src")):
            parent = os.path.dirname(curr)
            if parent == curr:
                curr = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
                break
            curr = parent
        base_dir = curr
        load_dotenv(os.path.join(base_dir, '.env'), override=True)
        
        if _playwright_ctx is None:
            _playwright_ctx = await async_playwright().start()
            
        cdp_url = os.getenv("BROWSER_CDP_URL", "").strip()
        if cdp_url:
            # Check if local port (e.g. 9222) is open
            try:
                port = 9222
                if ":" in cdp_url:
                    port = int(cdp_url.split(":")[-1].strip("/"))
                
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    port_open = (s.connect_ex(('127.0.0.1', port)) == 0)
            except Exception:
                port_open = False
                
            if not port_open and ("localhost" in cdp_url or "127.0.0.1" in cdp_url):
                print(f"🌐 [Browser] CDP port {port} is closed. Auto-launching Brave in debugging mode...", flush=True)
                exec_path = os.getenv("BROWSER_EXECUTABLE_PATH", "/usr/bin/brave")
                exec_path = os.path.expanduser(exec_path)
                
                user_data = os.getenv("BROWSER_USER_DATA_DIR", "").strip()
                if not user_data:
                    user_data = "~/.config/brave-assistant-profile"
                user_data = os.path.expanduser(user_data)
                os.makedirs(user_data, exist_ok=True)
                
                subprocess.Popen(
                    [exec_path, f"--remote-debugging-port={port}", f"--user-data-dir={user_data}", "--no-first-run"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                await asyncio.sleep(3) # Wait for Brave to initialize
            
            try:
                _browser = await _playwright_ctx.chromium.connect_over_cdp(cdp_url)
                # Select the first page or create a context if empty
                if _browser.contexts:
                    _browser_context = _browser.contexts[0]
                    if _browser_context.pages:
                        _page = _browser_context.pages[0]
                    else:
                        _page = await _browser_context.new_page()
                else:
                    _browser_context = await _browser.new_context()
                    _page = await _browser_context.new_page()
            except Exception as connect_err:
                print(f"⚠️ Connection over CDP failed: {connect_err}. Launching local fallback...", flush=True)
                _browser = None
                
        if _browser is None:
            _browser = await _playwright_ctx.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            _browser_context = await _browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            await _apply_stealth_scripts(_browser_context)
            _page = await _browser_context.new_page()
            
    return _page

DOM_MAP_SCRIPT = """
() => {
    // Resolve the semantic role of an element
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

    // Resolve human-readable label for an element
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

        // Skip zero-size or off-screen
        if (rect.width <= 0 || rect.height <= 0) continue;

        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) continue;

        const tag = el.tagName.toUpperCase();
        const isStandardInteractive = ['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(tag);
        const ariaRole = el.getAttribute('role') || '';
        const hasInteractiveRole = ['button', 'link', 'checkbox', 'radio', 'tab', 'option',
                                    'menuitem', 'textbox', 'searchbox', 'combobox', 'listbox',
                                    'spinbutton'].includes(ariaRole);
        const hasClickAttr = el.hasAttribute('onclick') || el.getAttribute('tabindex') === '0';
        const hasCursorPointer = style.cursor === 'pointer';

        if (isStandardInteractive || hasInteractiveRole || hasClickAttr || hasCursorPointer) {
            candidates.push({ el, rect });
        }
    }

    // De-duplicate: skip elements that are fully contained within a BUTTON or A ancestor
    let idCounter = 0;
    const result = [];

    candidates.forEach(({ el, rect }) => {
        let ancestor = el.parentElement;
        while (ancestor) {
            const aTag = ancestor.tagName.toUpperCase();
            if (['BUTTON', 'A'].includes(aTag) && candidates.some(c => c.el === ancestor)) {
                return; // skip, parent already captures this element
            }
            ancestor = ancestor.parentElement;
        }

        const label = getLabel(el);
        // Drop no-label decorative elements (except inputs which may have no visible text)
        const tag = el.tagName.toUpperCase();
        if (!label && !['INPUT', 'SELECT', 'TEXTAREA'].includes(tag)) return;

        const cx = Math.round(rect.x + rect.width / 2);
        const cy = Math.round(rect.y + rect.height / 2);

        // Stamp data-agent-id so click tools can still use selector-based clicking
        el.setAttribute('data-agent-id', idCounter.toString());

        result.push({
            id: idCounter++,
            tag: el.tagName.toLowerCase(),
            type: el.type || '',
            role: getRole(el),
            label: label,
            x: cx,
            y: cy,
            width: Math.round(rect.width),
            height: Math.round(rect.height)
        });
    });

    return result;
}
"""

async def _get_dom_map(offset: int = 0, limit: int = 30, filter_role: str = None) -> str:
    """Internal helper: run DOM_MAP_SCRIPT on the current page and return a compact formatted string."""
    page = await _get_browser_page()
    try:
        elements = await page.evaluate(DOM_MAP_SCRIPT)
        if not elements:
            return "No interactive elements found on this page."

        if filter_role:
            elements = [e for e in elements if e['role'] == filter_role]

        total_elements = len(elements)
        paginated = elements[offset:offset + limit]

        if not paginated:
            return (
                f"No elements found in range [{offset}–{offset+limit}]. "
                f"(Total: {total_elements})"
            )

        lines = []
        for el in paginated:
            label_str = f'"{el["label"]}"' if el['label'] else '(no label)'
            lines.append(
                f'[{el["id"]}] {el["role"]} {label_str} '
                f'at ({el["x"]}, {el["y"]}) {el["width"]}\u00d7{el["height"]}'
            )

        header = (
            f"DOM map — showing {offset}–{offset + len(paginated) - 1} of {total_elements} elements"
            + (f" (filtered: role='{filter_role}')" if filter_role else "")
            + ". Use offset/limit to paginate.\n"
        )
        return header + "\n".join(lines)
    except Exception as e:
        return f"Error building DOM map: {e}"
