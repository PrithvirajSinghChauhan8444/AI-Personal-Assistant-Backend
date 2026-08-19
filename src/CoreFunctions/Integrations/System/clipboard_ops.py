import subprocess
import shutil
import os

def copy_to_clipboard(text: str) -> str:
    """Copies text to the system clipboard using wl-copy, xclip, or xsel.
    
    Args:
        text (str): The text content to copy.
    """
    # Try Wayland (wl-copy) first if running on Wayland or if wl-copy is installed
    if shutil.which("wl-copy") and (os.environ.get("WAYLAND_DISPLAY") or not shutil.which("xclip")):
        try:
            p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, text=True)
            p.communicate(input=text)
            return "Successfully copied text to system clipboard using wl-copy."
        except Exception as e:
            # Fall through to try X11 tools
            pass

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
    elif shutil.which("wl-copy"):  # Fallback to wl-copy even if WAYLAND_DISPLAY environment variable is not explicitly set
        try:
            p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, text=True)
            p.communicate(input=text)
            return "Successfully copied text to system clipboard using wl-copy."
        except Exception as e:
            return f"Failed to copy to clipboard using wl-copy: {e}"
    else:
        return "❌ Clipboard Error: Neither 'wl-copy', 'xclip' nor 'xsel' is installed on your Linux system. Please install 'wl-clipboard' (Wayland) or 'xclip'/'xsel' (X11) to enable clipboard access."

def paste_from_clipboard() -> str:
    """Retrieves and returns text from the system clipboard using wl-paste, xclip, or xsel."""
    # Try Wayland (wl-paste) first if running on Wayland or if wl-paste is installed
    if shutil.which("wl-paste") and (os.environ.get("WAYLAND_DISPLAY") or not shutil.which("xclip")):
        try:
            res = subprocess.check_output(["wl-paste", "--no-newline"], text=True, stderr=subprocess.PIPE)
            return res
        except Exception as e:
            # Fall through to X11 tools
            pass

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
    elif shutil.which("wl-paste"):  # Fallback to wl-paste even if WAYLAND_DISPLAY environment variable is not explicitly set
        try:
            res = subprocess.check_output(["wl-paste", "--no-newline"], text=True, stderr=subprocess.PIPE)
            return res
        except Exception as e:
            return f"Failed to paste from clipboard using wl-paste: {e}"
    else:
        return "❌ Clipboard Error: Neither 'wl-paste', 'xclip' nor 'xsel' is installed on your Linux system. Please install 'wl-clipboard' (Wayland) or 'xclip'/'xsel' (X11) to enable clipboard access."
