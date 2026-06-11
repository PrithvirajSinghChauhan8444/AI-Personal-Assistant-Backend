import subprocess
import shutil

def copy_to_clipboard(text: str) -> str:
    """Copies text to the system clipboard using xclip or xsel.
    
    Args:
        text (str): The text content to copy.
    """
    if shutil.which("xclip"):
        try:
            p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, text=True)
            p.communicate(input=text)
            return "Successfully copied text to system clipboard using xclip."
        except Exception as e:
            return f"Failed to copy to clipboard using xclip: {e}"
    elif shutil.which("xsel"):
        try:
            p = subprocess.Popen(["xsel", "--clipboard", "--input"], stdin=subprocess.PIPE, text=True)
            p.communicate(input=text)
            return "Successfully copied text to system clipboard using xsel."
        except Exception as e:
            return f"Failed to copy to clipboard using xsel: {e}"
    else:
        return "❌ Clipboard Error: Neither 'xclip' nor 'xsel' is installed on your Linux system. Please run 'sudo apt install xclip' to enable clipboard access."

def paste_from_clipboard() -> str:
    """Retrieves and returns text from the system clipboard using xclip or xsel."""
    if shutil.which("xclip"):
        try:
            res = subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], text=True, stderr=subprocess.PIPE)
            return res
        except subprocess.CalledProcessError as e:
            # If the clipboard selection is empty or has non-text data, xclip returns non-zero status
            if "target" in e.stderr.lower() or not e.output:
                return ""
            return f"Failed to paste from clipboard: {e.stderr}"
        except Exception as e:
            return f"Failed to paste from clipboard: {e}"
    elif shutil.which("xsel"):
        try:
            res = subprocess.check_output(["xsel", "--clipboard", "--output"], text=True, stderr=subprocess.PIPE)
            return res
        except subprocess.CalledProcessError as e:
            if not e.output:
                return ""
            return f"Failed to paste from clipboard: {e.stderr}"
        except Exception as e:
            return f"Failed to paste from clipboard using xsel: {e}"
    else:
        return "❌ Clipboard Error: Neither 'xclip' nor 'xsel' is installed on your Linux system. Please run 'sudo apt install xclip' to enable clipboard access."
