import html
import re
from typing import List

TELEGRAM_MAX_CHUNK_SIZE = 3500


def split_markdown(text: str, max_length: int = TELEGRAM_MAX_CHUNK_SIZE) -> List[str]:
    """
    Splits markdown text into clean chunks under max_length,
    preserving code blocks across chunk boundaries.
    """
    if not text:
        return [""]

    if len(text) <= max_length:
        return [text]

    chunks: List[str] = []
    lines = text.split("\n")
    current_chunk = ""
    in_code_block = False
    code_block_lang = ""

    for line in lines:
        code_fence_match = re.match(r"^```(\w*)", line.strip())
        is_fence = bool(code_fence_match)

        line_to_add = line + "\n"

        if len(current_chunk) + len(line_to_add) > max_length:
            if current_chunk:
                if in_code_block:
                    current_chunk += "```\n"
                    chunks.append(current_chunk.strip())
                    current_chunk = f"```{code_block_lang}\n{line_to_add}"
                else:
                    chunks.append(current_chunk.strip())
                    current_chunk = line_to_add
            else:
                # Line itself exceeds max_length
                for i in range(0, len(line), max_length):
                    chunks.append(line[i : i + max_length])
                current_chunk = ""
        else:
            current_chunk += line_to_add

        if is_fence:
            if not in_code_block:
                in_code_block = True
                code_block_lang = code_fence_match.group(1) if code_fence_match else ""
            else:
                in_code_block = False
                code_block_lang = ""

    if current_chunk.strip():
        if in_code_block and not current_chunk.strip().endswith("```"):
            current_chunk += "\n```"
        chunks.append(current_chunk.strip())

    return chunks


def markdown_to_telegram_html(text: str) -> str:
    """
    Converts standard Markdown/CommonMark to Telegram-compatible HTML.
    Handles headers, bold, italics, code blocks, inline code, links, and lists
    while escaping dangerous characters.
    """
    if not text:
        return ""

    # 1. Extract and placeholder multiline code blocks
    code_blocks = []

    def replace_code_block(match):
        lang = match.group(1) or ""
        code = match.group(2)
        # Escape HTML inside code
        code_escaped = html.escape(code.strip("\n"))
        if lang:
            replacement = f'<pre><code class="language-{lang}">{code_escaped}</code></pre>'
        else:
            replacement = f"<pre><code>{code_escaped}</code></pre>"
        code_blocks.append(replacement)
        return f"%%TELEGRAM_CODE_BLOCK_{len(code_blocks)-1}%%"

    text = re.sub(r"```(\w*)\n?(.*?)```", replace_code_block, text, flags=re.DOTALL)

    # 2. Extract and placeholder inline code
    inline_codes = []

    def replace_inline_code(match):
        code = match.group(1)
        inline_codes.append(f"<code>{html.escape(code)}</code>")
        return f"%%TELEGRAM_INLINE_CODE_{len(inline_codes)-1}%%"

    text = re.sub(r"`([^`\n]+)`", replace_inline_code, text)

    # 3. Escape HTML characters in remaining text
    text = html.escape(text)

    # 4. Headers: # Header -> <b>Header</b>
    text = re.sub(r"(?m)^#{1,6}\s+(.+)$", r"<b>\1</b>", text)

    # 5. Bold: **bold** or __bold__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    # 6. Italic: *italic* (bounded by non-word chars to avoid breaking snake_case variables)
    text = re.sub(r"(?<!\w)\*([^\*\n]+?)\*(?!\w)", r"<i>\1</i>", text)

    # 7. Convert Markdown links: [Title](https://...) -> <a href="url">Title</a>
    # Note: URL has & escaped from html.escape, which is valid in HTML attributes
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", r'<a href="\2">\1</a>', text)

    # 8. Clean bullet points: * or - at start of line -> •
    text = re.sub(r"(?m)^[\*\-]\s+", "• ", text)

    # 9. Restore placeholders
    for i, code in enumerate(inline_codes):
        text = text.replace(f"%%TELEGRAM_INLINE_CODE_{i}%%", code)
    for i, block in enumerate(code_blocks):
        text = text.replace(f"%%TELEGRAM_CODE_BLOCK_{i}%%", block)

    return text
