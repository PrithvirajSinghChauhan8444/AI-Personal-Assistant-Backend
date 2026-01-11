import subprocess
import os

DOCKER_COMPOSE_FILE = os.path.join(os.path.dirname(__file__), "docker-compose.yml")

def start_waha():
    """Starts the WAHA docker container."""
    try:
        subprocess.run(["docker-compose", "-f", DOCKER_COMPOSE_FILE, "up", "-d"], check=True)
        return "WAHA Server Started (Docker)."
    except Exception as e:
        return f"Failed to start WAHA: {e}"

def stop_waha():
    """Stops the WAHA docker container."""
    try:
        subprocess.run(["docker-compose", "-f", DOCKER_COMPOSE_FILE, "down"], check=True)
        return "WAHA Server Stopped."
    except Exception as e:
        return f"Failed to stop WAHA: {e}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "start":
            print(start_waha())
        elif cmd == "stop":
            print(stop_waha())
        else:
            print("Usage: python manage.py [start|stop]")
    else:
        print("Usage: python manage.py [start|stop]")
