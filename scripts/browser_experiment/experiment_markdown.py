import os
import sys
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from playwright.async_api import async_playwright

# Load env variables
load_dotenv()

# Setup LLM
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
if not api_key:
    print("❌ ERROR: GEMINI_API_KEY is not set in your environment or .env file.")
    sys.exit(1)

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0
)

# Playwright Global Context
_playwright = None
_browser = None
_page = None

async def _get_page():
    global _playwright, _browser, _page
    if _page is None:
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=False,  # Set to False to watch it work!
            slow_mo=1000     # Slow down slightly so we can observe
        )
        _page = await _browser.new_page()
    return _page

# JS Script to traverse DOM and compile a clean Markdown representation
HTML_TO_MARKDOWN_SCRIPT = """
() => {
    function cleanNode(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            return node.textContent;
        }
        if (node.nodeType !== Node.ELEMENT_NODE) {
            return "";
        }
        
        const tagName = node.tagName.toLowerCase();
        if (["script", "style", "head", "iframe", "noscript", "svg", "header", "footer", "nav"].includes(tagName)) {
            return "";
        }
        
        // Filter hidden elements
        const style = window.getComputedStyle(node);
        if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
            return "";
        }
        
        let childrenContent = "";
        for (let child of node.childNodes) {
            childrenContent += cleanNode(child);
        }
        childrenContent = childrenContent.trim();
        if (!childrenContent) return "";
        
        // Add CSS cues to help the agent find selectors
        let selectorCue = "";
        if (node.id) {
            selectorCue = ` {#${node.id}}`;
        } else if (node.name) {
            selectorCue = ` {[name="${node.name}"]} `;
        } else if (tagName === "input" && node.placeholder) {
            selectorCue = ` {[placeholder="${node.placeholder}"]} `;
        }
        
        switch (tagName) {
            case "h1": return `\\n# ${childrenContent}${selectorCue}\\n`;
            case "h2": return `\\n## ${childrenContent}${selectorCue}\\n`;
            case "h3": return `\\n### ${childrenContent}${selectorCue}\\n`;
            case "h4": return `\\n#### ${childrenContent}${selectorCue}\\n`;
            case "p": return `\\n${childrenContent}\\n`;
            case "a": return ` [${childrenContent}](${node.href || '#'}) `;
            case "li": return `\\n* ${childrenContent}`;
            case "strong":
            case "b": return ` **${childrenContent}** `;
            case "em":
            case "i": return ` *${childrenContent}* `;
            case "pre": return `\\n\`\`\`\\n${childrenContent}\\n\`\`\`\\n`;
            case "code": return ` \`${childrenContent}\` `;
            case "input":
                const type = node.type || "text";
                const ph = node.placeholder ? ` placeholder="${node.placeholder}"` : "";
                const nm = node.name ? ` name="${node.name}"` : "";
                const nid = node.id ? ` id="${node.id}"` : "";
                return `\\n[INPUT: type="${type}"${nid}${nm}${ph}]\\n`;
            case "button":
                const bid = node.id ? ` id="${node.id}"` : "";
                return `\\n[BUTTON: "${childrenContent}"${bid}]\\n`;
            default:
                return childrenContent;
        }
    }
    
    // Process main body text
    return cleanNode(document.body).replace(/\\n\\s*\\n+/g, '\\n\\n').trim();
}
"""

async def get_page_markdown() -> str:
    page = await _get_page()
    try:
        markdown = await page.evaluate(HTML_TO_MARKDOWN_SCRIPT)
        return markdown if markdown else "Page contains no readable content."
    except Exception as e:
        return f"Error distilling Markdown: {e}"

# --- Tools for Markdown Agent (All async) ---

async def browser_navigate_markdown(url: str) -> str:
    """Navigates to the specified URL and returns the distilled Markdown content of the page."""
    print(f"\n[Tool: Navigate] Opening {url}...")
    page = await _get_page()
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        markdown_str = await get_page_markdown()
        return f"Successfully loaded {url}.\nPage Markdown Content:\n{markdown_str}"
    except Exception as e:
        return f"Error navigating to {url}: {e}"

async def click_selector(selector: str) -> str:
    """Clicks the element matching the provided CSS selector (e.g. 'button#search', 'a[href="/post"]')."""
    print(f"\n[Tool: Click] Clicking selector: {selector}...")
    page = await _get_page()
    try:
        await page.click(selector, timeout=5000)
        await page.wait_for_timeout(2000)
        markdown_str = await get_page_markdown()
        return f"Clicked selector '{selector}'. Updated Page Markdown:\n{markdown_str}"
    except Exception as e:
        return f"Error clicking selector '{selector}': {e}"

async def fill_selector(selector: str, text: str) -> str:
    """Enters text into the input field matching the provided CSS selector."""
    print(f"\n[Tool: Fill] Entering '{text}' into selector: {selector}...")
    page = await _get_page()
    try:
        await page.fill(selector, text, timeout=5000)
        await page.wait_for_timeout(1000)
        markdown_str = await get_page_markdown()
        return f"Filled selector '{selector}' with text. Updated Page Markdown:\n{markdown_str}"
    except Exception as e:
        return f"Error filling selector '{selector}': {e}"

async def read_page_content() -> str:
    """Re-reads the current browser page and returns its updated Markdown representation."""
    markdown_str = await get_page_markdown()
    return f"Current Page Markdown:\n{markdown_str}"

# Compile Agent
tools = [browser_navigate_markdown, click_selector, fill_selector, read_page_content]
agent = create_react_agent(
    llm, 
    tools, 
    prompt="""You are an experimental browser control agent using HTML-to-Markdown Distillation.
You navigate pages by reading clean Markdown pages containing inline CSS selectors cues like {#id} or [placeholder="x"].
Identify the appropriate elements to interact with and call click_selector(selector) or fill_selector(selector, text).
Always explain what you are doing in natural language before calling a tool.
"""
)

async def main():
    print("🤖 Enter your browser automation task (Markdown Agent):")
    print("Example: 'Go to https://news.ycombinator.com, find the search box, search for playwright, and print the top results.'")
    test_prompt = input("\nTask > ").strip()
    if not test_prompt:
        print("Empty task. Exiting.")
        return
    
    print(f"\n🚀 Running Async Markdown Agent Experiment...")
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
