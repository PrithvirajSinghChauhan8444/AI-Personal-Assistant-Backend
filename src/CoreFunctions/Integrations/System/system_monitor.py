import psutil

def get_system_stats():
    """
    Returns real-time system usage statistics.
    """
    # 1. CPU Usage
    cpu_usage = psutil.cpu_percent(interval=None) # interval=None for non-blocking

    # 2. RAM Usage
    memory = psutil.virtual_memory()
    ram_usage = memory.percent

    # 3. Disk Usage (C: Drive)
    # Windows usually uses 'C:\\', Linux/Mac uses '/'
    disk_path = 'C:\\' if psutil.WINDOWS else '/'
    disk = psutil.disk_usage(disk_path)
    disk_usage = disk.percent

    # 4. Battery (if laptop)
    battery = psutil.sensors_battery()
    if battery:
        battery_percent = battery.percent
        is_plugged = battery.power_plugged
        battery_status = "Charging" if is_plugged else "Discharging"
    else:
        battery_percent = 100
        battery_status = "AC Power"

    return {
        "cpu": cpu_usage,
        "ram": ram_usage,
        "disk": disk_usage,
        "battery": battery_percent,
        "status": battery_status
    }

# Test block
if __name__ == "__main__":
    print(get_system_stats())