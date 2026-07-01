import re
from html.parser import HTMLParser

class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return "".join(self.fed)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

def clean_body_content(raw_body: str) -> str:
    """Cleans an email body or snippet.
    
    Removes base64 images, style sheets, inline styles, script blocks, tracking pixels,
    converts HTML structure to plain text, normalizes newlines/whitespace, and truncates to 2,000 characters.
    """
    if not raw_body:
        return ""
        
    # 1. Strip base64 image blobs: src="data:image/...;base64,..."
    cleaned = re.sub(r'src=["\']data:image/[^"\']+;base64,[^"\']+["\']', 'src="[image blob skipped]"', raw_body, flags=re.IGNORECASE)
    cleaned = re.sub(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+', '[base64 image data]', cleaned)
    
    # 2. Strip inline CSS/style tags and their contents: <style>...</style>
    cleaned = re.sub(r'<style\b[^>]*>.*?</style>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    
    # 3. Strip script tags and their contents: <script>...</script>
    cleaned = re.sub(r'<script\b[^>]*>.*?</script>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    
    # 4. Strip tracking pixels (1x1 img tags or similar)
    cleaned = re.sub(r'<img\b[^>]*(?:width=["\']1["\']|height=["\']1["\'])[^*>]*>', '', cleaned, flags=re.IGNORECASE)
    
    # 5. Convert HTML to plain text using standard HTMLParser
    try:
        cleaned_text = strip_tags(cleaned)
    except Exception:
        cleaned_text = re.sub(r'<[^>]+>', ' ', cleaned)
        
    # 6. Strip excessive whitespace/newlines
    cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)
    cleaned_text = re.sub(r'[ \t]+', ' ', cleaned_text)
    cleaned_text = cleaned_text.strip()
    
    # 7. Truncate to 2000 chars with "... [truncated]" marker
    if len(cleaned_text) > 2000:
        cleaned_text = cleaned_text[:2000] + "\n... [truncated]"
        
    return cleaned_text
