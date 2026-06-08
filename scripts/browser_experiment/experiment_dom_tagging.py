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
        profile_directory = None
        if user_data_dir:
            user_data_dir = os.path.expanduser(user_data_dir)
            if browser_type_str == "chromium":
                basename = os.path.basename(user_data_dir)
                if basename == "Default" or basename.startswith("Profile "):
                    profile_directory = basename
                    user_data_dir = os.path.dirname(user_data_dir)
            
        executable_path = os.getenv("BROWSER_EXECUTABLE_PATH", "").strip()
        if executable_path:
            executable_path = os.path.expanduser(executable_path)
            
        headless_mode = os.getenv("BROWSER_HEADLESS", "True").lower() == "true"
        slow_mo_ms = int(os.getenv("BROWSER_SLOW_MO", "0"))
        
        browser_launcher = getattr(_playwright, browser_type_str)
        
        if _browser_context is None:
            if user_data_dir:
                launch_args = []
                if profile_directory:
                    launch_args.append(f"--profile-directory={profile_directory}")
                print(f"🌐 [Browser] Launching {browser_type_str} with persistent context at {user_data_dir} (profile={profile_directory or 'Default'}, headless={headless_mode}, slow_mo={slow_mo_ms}ms)...", flush=True)
                _browser_context = await browser_launcher.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=headless_mode,
                    slow_mo=slow_mo_ms,
                    executable_path=executable_path if executable_path else None,
                    args=launch_args
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

async def browser_read_page_content(mode: str = "summary", query: str = None, chunk_index: int = 0) -> str:
    """Reads or queries the textual content (paragraphs, headings, articles) of the current active browser tab.
    
    Args:
        mode (str): The reading mode:
            - 'summary': Uses a local model to summarize the main content of the page. Recommended for long pages.
            - 'query': Uses a local model to answer a specific question ('query') based on the page content.
            - 'chunk': Returns a specific paragraph/text chunk of the page (specified by 'chunk_index') to keep context small.
            - 'metadata': Returns title, URL, and a quick snippet.
        query (str, optional): The question to answer about the page content (only used when mode='query').
        chunk_index (int): The zero-based index of the text chunk to retrieve (only used when mode='chunk'). Each chunk is roughly 1500 words.
    """
    print(f"\n[Tool: Read Content] mode={mode}, query={query}, chunk_index={chunk_index}...")
    try:
        page = await _get_page()
        url = page.url
        title = await page.title()
        
        script = """
        () => {
            const elements = document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, article, section');
            const texts = [];
            elements.forEach(el => {
                if (el.closest('nav') || el.closest('footer') || el.closest('header') || el.closest('script') || el.closest('style')) {
                    return;
                }
                const text = el.innerText.trim();
                if (text && text.length > 20) {
                    texts.push(text);
                }
            });
            return texts.join('\\n\\n');
        }
        """
        full_text = await page.evaluate(script)
        if not full_text:
            return f"Page Title: {title}\nURL: {url}\nNo readable text content found on this page."
            
        words = full_text.split()
        chunk_size = 1500
        total_chunks = (len(words) + chunk_size - 1) // chunk_size
        
        if mode == "metadata":
            snippet = " ".join(words[:100])
            return f"Title: {title}\nURL: {url}\nTotal Words: {len(words)}\nTotal Chunks: {total_chunks}\nSnippet: {snippet}..."
            
        elif mode == "chunk":
            if chunk_index < 0 or chunk_index >= total_chunks:
                return f"Error: chunk_index {chunk_index} is out of range. Total chunks available: {total_chunks}."
            start_word = chunk_index * chunk_size
            end_word = start_word + chunk_size
            chunk_text = " ".join(words[start_word:end_word])
            return f"Chunk {chunk_index + 1}/{total_chunks} of page content (Title: {title}, URL: {url}):\n\n{chunk_text}"
            
        elif mode == "summary":
            try:
                from langchain_ollama import ChatOllama
                local_llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "gemma4:e2b"), temperature=0)
            except Exception:
                local_llm = None
                
            if not local_llm:
                chunk_text = " ".join(words[:chunk_size])
                return f"[Local LLM not available. Returning first chunk of {total_chunks} chunks] Page Content:\n\n{chunk_text}"
                
            prompt = f"Summarize the following text content from the webpage '{title}' ({url}) concisely, extracting the key points and main arguments:\n\n{full_text[:12000]}"
            try:
                response = await local_llm.ainvoke(prompt)
                return f"Summary of the webpage '{title}' (generated by local model):\n\n{response.content}"
            except Exception as e:
                chunk_text = " ".join(words[:chunk_size])
                return f"[Local LLM error: {e}. Returning first chunk of {total_chunks} chunks] Page Content:\n\n{chunk_text}"
                
        elif mode == "query":
            if not query:
                return "Error: mode='query' requires a 'query' argument."
            try:
                from langchain_ollama import ChatOllama
                local_llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "gemma4:e2b"), temperature=0)
            except Exception:
                local_llm = None
                
            if not local_llm:
                chunk_text = " ".join(words[:chunk_size])
                return f"[Local LLM not available. Returning first chunk for manual query: '{query}'] Page Content:\n\n{chunk_text}"
                
            prompt = f"Based on the following text content from the webpage '{title}', answer this question: '{query}'. Provide a concise and accurate answer based only on the text.\n\nContent:\n{full_text[:12000]}"
            try:
                response = await local_llm.ainvoke(prompt)
                return f"Answer (generated by local model): {response.content}"
            except Exception as e:
                chunk_text = " ".join(words[:chunk_size])
                return f"[Local LLM error: {e}. Returning first chunk for manual search: '{query}'] Page Content:\n\n{chunk_text}"
        else:
            return f"Error: Invalid mode '{mode}'."
    except Exception as e:
        return f"Error extracting page text content: {e}"

async def request_human_intervention(reason: str) -> str:
    """Pauses the automated process and requests manual intervention from the human user.
    
    Use this tool when:
    - You encounter a CAPTCHA, Cloudflare verification, or bot detection.
    - You need a 2FA / OTP code, or the user needs to log in manually.
    - You are stuck, encounter a roadblock, or need clarification on how to proceed.
    
    Args:
        reason (str): The specific reason or barrier you encountered.
    """
    print(f"\n🚨 [HUMAN INTERVENTION REQUESTED] 🚨", flush=True)
    print(f"Reason: {reason}", flush=True)
    print(f"👉 Please perform any necessary actions in the open browser window.", flush=True)
    
    # Run the input call in a separate thread so we don't block the async event loop
    user_input = await asyncio.to_thread(
        input, 
        "\nPress [Enter] when done, or type a message/code to send back to the agent: "
    )
    user_input = user_input.strip()
    if not user_input:
        user_input = "done"
    print(f"✅ Resuming automation. User responded: '{user_input}'\n", flush=True)
    return f"Human responded: {user_input}"

# Compile Agent
tools = [browser_navigate, click_element, fill_element, get_page_state, browser_read_page_content, request_human_intervention]
agent = create_react_agent(
    llm, 
    tools, 
    prompt="""You are an experimental browser control agent using DOM Element Tagging.
You navigate pages by looking at lists of interactive elements containing numerical IDs.
To click a button or link, call click_element(element_id=ID).
To enter text, call fill_element(element_id=ID, text="your input").
To read page textual content, call browser_read_page_content(mode="summary", query="...", chunk_index=0).

HUMAN INTERVENTION GUIDELINES:
- If you encounter a CAPTCHA, Cloudflare bot check, or "Verify you are human" test, immediately call `request_human_intervention` explaining the situation.
- If you encounter a 2FA/OTP code screen, or need the user to manually log in/approve a screen, call `request_human_intervention`.
- If you are stuck, cannot find the right elements, or encounter a roadblock, call `request_human_intervention`.
- If the user's prompt explicitly asks you to pause, wait, or let them perform a manual action (e.g. "let me play the video", "let me choose", "wait for me"), you MUST call `request_human_intervention` to hand control over to them.
- If a website requires or works better with a sign-in, check if you are already logged in; if not, call `request_human_intervention` to let the user log in first.
- DO NOT try to solve CAPTCHAs yourself. Always delegate them to the human.
- CRITICAL: Do not finish the task or output a final answer before the human does their part. Call `request_human_intervention` first, and once that tool returns, call `get_page_state` (or look at updated elements) to inspect what changed, and then proceed with the rest of the user's task.

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
