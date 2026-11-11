"""Executable daemon entrypoint for Layer 4 Python Cognitive Plane."""

import asyncio
import os
import signal
import sys
from typing import Optional

from dotenv import load_dotenv

from src.bridge.daemon.bridge import AgentRunner, PythonBridgeDaemon
from src.bridge.daemon.transport import AsyncNDJSONTransport

load_dotenv("config/.env")
load_dotenv(".env")


async def run_daemon(agent_runner: Optional[AgentRunner] = None) -> None:
    """Initializes and runs the resident daemon until stdin closes."""
    transport = AsyncNDJSONTransport()
    await transport.initialize()

    daemon = PythonBridgeDaemon(transport=transport, agent_runner=agent_runner)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(transport.close()))
        except (NotImplementedError, RuntimeError):
            pass

    transport.log_diagnostic("Python daemon initialized; entering event loop.")
    await daemon.run()
    transport.log_diagnostic("Python daemon cleanly terminated; exiting 0.")


def main() -> None:
    """Main execution point for `python -m src.bridge.daemon`."""
    try:
        asyncio.run(run_daemon())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as exc:
        sys.stderr.write(f"[Layer4-Daemon-Fatal] {exc}\n")
        sys.stderr.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
