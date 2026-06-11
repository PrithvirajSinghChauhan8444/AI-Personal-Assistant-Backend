import subprocess
import shutil
import os

def download_file(url: str, save_dir: str = "./Downloads", filename: str = None) -> str:
    """Downloads a file from a URL using aria2c.
    
    Args:
        url (str): The HTTP/HTTPS download link.
        save_dir (str): The directory to save the file. Defaults to './Downloads'.
        filename (str, optional): Rename the downloaded file. Defaults to None.
    """
    os.makedirs(save_dir, exist_ok=True)
    
    # Base command
    cmd = ["aria2c", "--summary-interval=1", "-d", save_dir]
    if filename:
        cmd += ["-o", filename]
    cmd.append(url)
    
    # Check if aria2c is installed
    if not shutil.which("aria2c"):
        return "❌ Error: 'aria2c' is not installed on the system. Please run 'sudo apt install aria2' first to enable downloads."
        
    try:
        # Run aria2c and block until completion
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        
        # Determine output filename
        dest_filename = filename
        if not dest_filename:
            # Try to grab it from URL basename
            basename = os.path.basename(url.split('?')[0])
            dest_filename = basename if basename else "downloaded_file"
            
        full_path = os.path.abspath(os.path.join(save_dir, dest_filename))
        return f"Successfully downloaded file to: {full_path}"
    except subprocess.CalledProcessError as e:
        err = e.stderr.strip() if e.stderr else e.stdout.strip()
        return f"Download failed. aria2c error: {err}"
    except Exception as e:
        return f"An unexpected error occurred during download: {e}"
