import os
import sys
import pytest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from modules.adapters.telegram.formatter import (
    markdown_to_telegram_html,
    split_markdown,
)


class TestTelegramFormatter:
    def test_headers_conversion(self):
        md = "# Main Header\nSome text\n### Subheader\nMore text"
        html = markdown_to_telegram_html(md)
        assert "<b>Main Header</b>" in html
        assert "<b>Subheader</b>" in html

    def test_bold_and_italic(self):
        md = "This is **bold** and this is *italic* and __also bold__."
        html = markdown_to_telegram_html(md)
        assert "<b>bold</b>" in html
        assert "<i>italic</i>" in html
        assert "<b>also bold</b>" in html

    def test_snake_case_preserved_not_italicized(self):
        md = "Variables: user_id_value and process_name_str should stay normal."
        html = markdown_to_telegram_html(md)
        assert "<i>" not in html
        assert "user_id_value" in html
        assert "process_name_str" in html

    def test_code_blocks_and_html_entities(self):
        md = "Here is some code:\n```python\nif x < 10 and y > 2:\n    print('Hello <world>')\n```"
        html = markdown_to_telegram_html(md)
        assert '<pre><code class="language-python">' in html
        assert "if x &lt; 10 and y &gt; 2:" in html
        assert "print(&#x27;Hello &lt;world&gt;&#x27;)" in html or "print('Hello &lt;world&gt;')" in html

    def test_inline_code(self):
        md = "Use `config.get('api_key')` to read the value."
        html = markdown_to_telegram_html(md)
        assert "<code>config.get(&#x27;api_key&#x27;)</code>" in html or "<code>config.get('api_key')</code>" in html

    def test_links_conversion(self):
        md = "Check the [Google](https://google.com) documentation."
        html = markdown_to_telegram_html(md)
        assert '<a href="https://google.com">Google</a>' in html

    def test_bullet_points(self):
        md = "* Item 1\n* Item 2\n- Item 3"
        html = markdown_to_telegram_html(md)
        assert "• Item 1" in html
        assert "• Item 2" in html
        assert "• Item 3" in html

    def test_split_markdown(self):
        lines = [f"Section {i} with lots of text to fill up capacity." for i in range(100)]
        md = "\n\n".join(lines)
        chunks = split_markdown(md, max_length=500)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 500
            html = markdown_to_telegram_html(chunk)
            assert html
