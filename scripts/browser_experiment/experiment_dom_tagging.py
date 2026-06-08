import os
import sys
import json
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from playwright.async_api import async_playwright

# Load env variables
load_dotenv()

# Setup Cloud LLM
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
if not api_key:
    print("❌ ERROR: GEMINI_API_KEY is not set in your environment or .env file.")
    sys.exit(1)

print("🤖 Connecting to cloud Gemini model (gemini-3.1-flash-lite)...")
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0
)

# Playwright Global Context
_playwright = None
_browser = None
_page = None

_browser_context = None

async def _get_page():
    global _playwright, _browser, _browser_context, _page
    if _page is None or _page.is_closed():
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        if _playwright is None:
            _playwright = await async_playwright().start()
            
        cdp_url = os.getenv("BROWSER_CDP_URL", "").strip()
        if cdp_url:
            if _browser_context is None:
                print(f"🌐 [Browser] Connecting to active browser session over CDP at {cdp_url}...", flush=True)
                _browser = await _playwright.chromium.connect_over_cdp(cdp_url)
                _browser_context = _browser.contexts[0] if _browser.contexts else await _browser.new_context()
            
            # Reuse existing active page/tab if available
            if _browser_context.pages:
                _page = _browser_context.pages[-1]
            else:
                _page = await _browser_context.new_page()
            return _page
            
        browser_type_str = os.getenv("BROWSER_TYPE", "chromium").lower()
        if browser_type_str not in ["chromium", "firefox", "webkit"]:
            browser_type_str = "chromium"
            
        user_data_dir = os.getenv("BROWSER_USER_DATA_DIR", "").strip()
        if user_data_dir:
            user_data_dir = os.path.expanduser(user_data_dir)
            
        executable_path = os.getenv("BROWSER_EXECUTABLE_PATH", "").strip()
        if executable_path:
            executable_path = os.path.expanduser(executable_path)
            
        headless_mode = os.getenv("BROWSER_HEADLESS", "True").lower() == "true"
        slow_mo_ms = int(os.getenv("BROWSER_SLOW_MO", "0"))
        
        browser_launcher = getattr(_playwright, browser_type_str)
        
        if _browser_context is None:
            if user_data_dir:
                print(f"🌐 [Browser] Launching {browser_type_str} with persistent context at {user_data_dir} (headless={headless_mode}, slow_mo={slow_mo_ms}ms)...", flush=True)
                _browser_context = await browser_launcher.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=headless_mode,
                    slow_mo=slow_mo_ms,
                    executable_path=executable_path if executable_path else None
                )
            else:
                if _browser is None:
                    print(f"🌐 [Browser] Launching {browser_type_str} (headless={headless_mode}, slow_mo={slow_mo_ms}ms)...", flush=True)
                    launch_kwargs = {
                        "headless": headless_mode,
                        "slow_mo": slow_mo_ms,
                    }
                    if executable_path:
                        launch_kwargs["executable_path"] = executable_path
                    if browser_type_str == "chromium":
                        launch_kwargs["args"] = ["--password-store=basic"]
                    _browser = await browser_launcher.launch(**launch_kwargs)
                
                _browser_context = await _browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" if browser_type_str == "chromium" else None
                )
        
        _page = await _browser_context.new_page()
    return _page

# JS Script to distill the DOM, tag interactive elements, and return a clean list
DOM_TAGGING_SCRIPT = """
() => {
    // 1. Remove previous tags if any
    const oldTags = document.querySelectorAll('[data-agent-id]');
    oldTags.forEach(el => el.removeAttribute('data-agent-id'));

    const candidates = document.querySelectorAll(
        'button, a, input, select, textarea, [role="button"], [onclick], [tabindex="0"]'
    );
    
    let idCounter = 0;
    const interactiveElements = [];

    candidates.forEach(el => {
        // Filter out elements that are not visible or off-screen
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        const isVisible = rect.width > 0 && 
                          rect.height > 0 && 
                          style.display !== 'none' && 
                          style.visibility !== 'hidden' &&
                          style.opacity !== '0';
                          
        if (isVisible) {
            const id = idCounter++;
            el.setAttribute('data-agent-id', id.toString());
            
            // Build a friendly name / description
            let text = el.innerText.trim();
            if (!text && el.placeholder) text = el.placeholder.trim();
            if (!text && el.getAttribute('aria-label')) text = el.getAttribute('aria-label').trim();
            if (!text && el.value) text = el.value.trim();
            if (!text && el.title) text = el.title.trim();
            if (!text) text = el.name || "";
            
            interactiveElements.push({
                id: id,
                tag: el.tagName.toLowerCase(),
                type: el.type || "",
                text: text,
                role: el.getAttribute('role') || ""
            });
        }
    });

    return interactiveElements;
}
"""

async def get_elements_formatted() -> str:
    page = await _get_page()
    try:
        elements = await page.evaluate(DOM_TAGGING_SCRIPT)
        if not elements:
            return "No interactive elements found on this page."
        
        lines = []
        for el in elements:
            type_str = f" (type='{el['type']}')" if el['type'] else ""
            role_str = f" [role='{el['role']}']" if el['role'] else ""
            lines.append(f"[{el['id']}] {el['tag'].upper()}: \"{el['text']}\"{type_str}{role_str}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error gathering page elements: {e}"

# --- Tools for DOM Tagging Agent (All async) ---

async def browser_navigate(url: str) -> str:
    """Navigates to the specified URL and returns the list of tagged elements on the page."""
    print(f"\n[Tool: Navigate] Opening {url}...")
    page = await _get_page()
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)  # Let dynamic scripts settle
        elements_str = await get_elements_formatted()
        return f"Successfully loaded {url}.\nInteractive Elements on Page:\n{elements_str}"
    except Exception as e:
        return f"Error navigating to {url}: {e}"

async def click_element(element_id: int) -> str:
    """Clicks the interactive element matching the specified numerical element_id."""
    print(f"\n[Tool: Click] Clicking element ID: {element_id}...")
    page = await _get_page()
    try:
        selector = f'[data-agent-id="{element_id}"]'
        await page.click(selector, timeout=5000)
        await page.wait_for_timeout(2000)
        elements_str = await get_elements_formatted()
        return f"Clicked element [{element_id}]. Updated Interactive Elements:\n{elements_str}"
    except Exception as e:
        return f"Error clicking element [{element_id}]: {e}"

async def fill_element(element_id: int, text: str) -> str:
    """Enters text into the input field matching the specified numerical element_id."""
    print(f"\n[Tool: Fill] Entering '{text}' into element ID: {element_id}...")
    page = await _get_page()
    try:
        selector = f'[data-agent-id="{element_id}"]'
        await page.fill(selector, text, timeout=5000)
        await page.wait_for_timeout(1000)
        elements_str = await get_elements_formatted()
        return f"Filled element [{element_id}] with text. Updated Interactive Elements:\n{elements_str}"
    except Exception as e:
        return f"Error filling element [{element_id}]: {e}"

async def get_page_state() -> str:
    """Returns the current page URL, title, and interactive elements currently available on the page."""
    try:
        page = await _get_page()
        url = page.url
        title = await page.title()
        elements_str = await get_elements_formatted()
        return f"Current Page Title: {title}\nCurrent Page URL: {url}\n\nCurrent Page Elements:\n{elements_str}"
    except Exception as e:
        return f"Error reading page state: {e}"

# Compile Agent
tools = [browser_navigate, click_element, fill_element, get_page_state]
agent = create_react_agent(
    llm, 
    tools, 
    prompt="""You are an experimental browser control agent using DOM Element Tagging.
You navigate pages by looking at lists of interactive elements containing numerical IDs.
To click a button or link, call click_element(element_id=ID).
To enter text, call fill_element(element_id=ID, text="your input").
Always explain what you are doing in natural language before calling a tool.
"""
)

async def main():
    print("🤖 Enter your browser automation task (DOM Tagging Agent):")
    print("Example: 'Go to https://news.ycombinator.com, find the search box, search for playwright, and print the top results.'")
    test_prompt = input("\nTask > ").strip()
    if not test_prompt:
        print("Empty task. Exiting.")
        return
    
    print(f"\n🚀 Running Async DOM Tagging Agent Experiment...")
    print(f"Goal: {test_prompt}\n")
    
    global _playwright, _browser
    try:
        async for chunk in agent.astream({"messages": [HumanMessage(content=test_prompt)]}):
            for node_name, node_update in chunk.items():
                messages = node_update.get("messages", [])
                for msg in messages:
                    if msg.type == "ai" and msg.content:
                        print(f"\n🤖 Agent Thought:\n{msg.content}")
                    elif msg.type == "tool":
                        # Truncate response output to keep console tidy
                        output = msg.content
                        if len(output) > 400:
                            output = output[:400] + "\n... [Output Truncated] ..."
                        print(f"\n📥 Tool [{msg.name}] Output:\n{output}")
    finally:
        if _browser:
            print("\nShutting down Playwright browser...")
            await _browser.close()
        if _playwright:
            await _playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())
