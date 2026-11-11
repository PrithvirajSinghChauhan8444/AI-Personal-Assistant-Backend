"""Layer 2 Orchestrator - Manager Agent Module.

Manager is the solitary cognitive planning agent of Layer 2.
"""

from .manager import DEFAULT_WORKER_SPECS, ManagerAgent

__all__ = ["ManagerAgent", "DEFAULT_WORKER_SPECS"]
