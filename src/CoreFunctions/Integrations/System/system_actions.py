import subprocess
import psutil
import os

def run_command(cmd: list) -> str:
    """Helper to run a subprocess command and return output/error cleanly."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return res.stdout.strip()
        return f"Error (code {res.returncode}): {res.stderr.strip()}"
    except Exception as e:
        return f"Exception: {str(e)}"

# ==========================================
# 1. VOLUME CONTROLS (amixer / pamixer)
# ==========================================

def get_volume() -> str:
    """Gets the current system volume percentage."""
    # Try pamixer first (common on modern Wayland/Pulse/Pipewire setups)
    val = run_command(["pamixer", "--get-volume"])
    if "Exception" not in val and "Error" not in val:
        mute = run_command(["pamixer", "--get-mute"])
        is_muted = "Muted" if "true" in mute else "Unmuted"
        return f"Volume: {val}% ({is_muted})"
    
    # Fallback to amixer
    val = run_command(["amixer", "sget", "Master"])
    import re
    m = re.search(r"\[(\d+)%\]", val)
    if m:
        return f"Volume: {m.group(1)}%"
    return f"Failed to read volume: {val}"

def set_volume(level: int) -> str:
    """Sets the system volume to a specific percentage (0-100)."""
    level = max(0, min(100, level))
    val = run_command(["pamixer", "--set-volume", str(level)])
    if "Exception" not in val and "Error" not in val:
        return f"Volume successfully set to {level}%"
    
    # Fallback to amixer
    val = run_command(["amixer", "sset", "Master", f"{level}%"])
    if "Exception" not in val and "Error" not in val:
        return f"Volume successfully set to {level}% via amixer"
    return f"Failed to set volume: {val}"

def toggle_mute() -> str:
    """Toggles system mute status."""
    val = run_command(["pamixer", "--toggle-mute"])
    if "Exception" not in val and "Error" not in val:
        mute = run_command(["pamixer", "--get-mute"])
        status = "Muted" if "true" in mute else "Unmuted"
        return f"System volume is now {status}"
    
    # Fallback to amixer
    val = run_command(["amixer", "sset", "Master", "toggle"])
    if "Exception" not in val and "Error" not in val:
        return "System volume muted/unmuted toggled via amixer"
    return f"Failed to toggle mute: {val}"

# ==========================================
# 2. BRIGHTNESS CONTROLS (brightnessctl)
# ==========================================

def get_brightness() -> str:
    """Gets the current screen brightness percentage."""
    val = run_command(["brightnessctl", "g"])
    max_val = run_command(["brightnessctl", "m"])
    try:
        curr = int(val)
        mx = int(max_val)
        pct = int((curr / mx) * 100)
        return f"Screen Brightness: {pct}%"
    except Exception:
        return f"Failed to read brightness: {val}"

def set_brightness(level: int) -> str:
    """Sets the screen brightness to a specific percentage (0-100)."""
    level = max(1, min(100, level)) # Avoid 0 to keep screen visible
    val = run_command(["brightnessctl", "s", f"{level}%"])
    if "Exception" not in val and "Error" not in val:
        return f"Screen brightness successfully set to {level}%"
    return f"Failed to set brightness: {val}"

# ==========================================
# 3. MEDIA PLAYBACK CONTROLS (playerctl)
# ==========================================

def media_control(action: str) -> str:
    """Controls background music media players (play-pause, next, previous)."""
    action = action.lower()
    if action not in ["play-pause", "next", "previous"]:
        return "Invalid action. Supported actions: 'play-pause', 'next', 'previous'"
    
    val = run_command(["playerctl", action])
    if "Exception" not in val and "Error" not in val:
        return f"Media control successful: Sent '{action}' to active player"
    return f"Failed to control media: {val} (Make sure playerctl is running and a player is active)"

# ==========================================
# 4. PROCESS MANAGEMENT (psutil)
# ==========================================

def list_processes(limit: int = 15) -> str:
    """Lists the top running processes sorted by memory usage."""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    # Sort by memory percent
    processes = sorted(processes, key=lambda x: x['memory_percent'] or 0, reverse=True)[:limit]
    
    res = ["PID    | Process Name       | CPU%  | MEM%"]
    res.append("-" * 45)
    for p in processes:
        res.append(f"{p['pid']:<6} | {p['name'][:18]:<18} | {p['cpu_percent']:<5} | {round(p['memory_percent'], 2)}%")
    return "\n".join(res)

def kill_process(name_or_pid: str) -> str:
    """Kills a running process by its PID or name."""
    try:
        # Check if argument is a PID
        pid = int(name_or_pid)
        proc = psutil.Process(pid)
        proc.terminate()
        return f"Process PID {pid} ({proc.name()}) terminated successfully"
    except ValueError:
        # Argument is a process name
        name = name_or_pid.lower()
        killed = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if name in proc.info['name'].lower():
                    proc.terminate()
                    killed.append(f"{proc.info['name']} (PID {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed:
            return f"Successfully terminated processes: {', '.join(killed)}"
        return f"No running processes found matching name: '{name_or_pid}'"
    except Exception as e:
        return f"Error terminating process: {e}"

# ==========================================
# 5. OS POWER / SECURITY ACTIONS
# ==========================================

def lock_screen() -> str:
    """Locks the current desktop session (Hyprland / Sway / General X11)."""
    # Try Hyprland / Sway lockers first
    for cmd in [["hyprlock"], ["swaylock"], ["betterlockscreen", "-l"], ["i3lock"]]:
        val = run_command(cmd)
        if "Exception" not in val and "Error" not in val:
            return "Screen locked successfully"
    return "Failed to lock screen: No compatible screen locker found (installed hyprlock/swaylock/i3lock required)"

def suspend_system() -> str:
    """Suspends the local system to RAM."""
    val = run_command(["systemctl", "suspend"])
    if "Exception" not in val and "Error" not in val:
        return "System suspension command sent successfully"
    return f"Failed to suspend system: {val}"
