"""Manager Agent package.

Note: In accordance with Layer 2 Orchestrator architecture, the Manager Agent
resides in the Orchestrator layer as its sole cognitive planning agent.
Canonical implementation: `src.orchestrator.manager`.
"""

from src.orchestrator.manager import ManagerAgent

__all__ = ["ManagerAgent"]
