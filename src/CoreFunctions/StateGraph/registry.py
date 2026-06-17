import os
import sys
import importlib
from abc import ABC, abstractmethod
from typing import Dict, List, Callable, Type
from src.CoreFunctions.StateGraph.state import AgentState

class BaseWorker(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the worker (e.g. 'GmailWorker')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description for the TaskRouter prompt."""
        pass

    @property
    @abstractmethod
    def instructions(self) -> str:
        """Detailed system prompt instructions for the worker agent."""
        pass

    @property
    @abstractmethod
    def tools(self) -> list:
        """List of tools assigned to this worker."""
        pass

    @property
    @abstractmethod
    def categories(self) -> List[str]:
        """List of categories associated with this worker (for loading skills)."""
        pass

    @property
    def use_local_llm(self) -> bool:
        """Flag to use local Ollama model instead of Gemini."""
        return False

    @property
    def is_graph_node(self) -> bool:
        """Whether this worker should be exposed as a top-level node in the main LangGraph and router."""
        return True

    def execute(self, state: AgentState) -> dict:
        """Execution node function added to the LangGraph."""
        # Import dynamically to prevent circular imports
        from src.CoreFunctions.StateGraph.executor import _execute_worker_node
        return _execute_worker_node(state, self.name)

class WorkerRegistry:
    _registry: Dict[str, BaseWorker] = {}

    @classmethod
    def register(cls, worker_cls: Type[BaseWorker]) -> Type[BaseWorker]:
        """Class decorator to register a BaseWorker subclass."""
        if not issubclass(worker_cls, BaseWorker):
            raise TypeError(f"Registered class {worker_cls.__name__} must inherit from BaseWorker")
        
        # Instantiate the worker to validate properties and register it
        try:
            worker_instance = worker_cls()
        except TypeError as e:
            raise TypeError(f"Failed to instantiate {worker_cls.__name__}. Ensure all abstract properties are implemented: {e}")
        
        cls._registry[worker_instance.name] = worker_instance
        return worker_cls

    @classmethod
    def get_all_workers(cls) -> Dict[str, BaseWorker]:
        """Returns the dictionary of registered worker instances."""
        return cls._registry

    @classmethod
    def get_worker_names(cls) -> List[str]:
        """Returns a sorted list of registered worker names."""
        return sorted(list(cls._registry.keys()))

    @classmethod
    def get_worker(cls, name: str) -> BaseWorker:
        """Retrieves a registered worker instance by name."""
        if name not in cls._registry:
            raise KeyError(f"Worker '{name}' is not registered.")
        return cls._registry[name]

def scan_and_register_workers(workers_dir: str = None):
    """Dynamically walks and imports all python files inside the workers directory to trigger registration decorators."""
    if workers_dir is None:
        workers_dir = os.path.join(os.path.dirname(__file__), "Workers")
        
    if not os.path.exists(workers_dir):
        return
        
    # We want to add the parent of the src/ directory to path if not present
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(workers_dir)))) # Project root
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
        
    for root, _, files in os.walk(workers_dir):
        for file in files:
            if file.endswith("_worker.py") and not file.startswith("__"):
                # Compute relative path from parent_dir
                rel_path = os.path.relpath(os.path.join(root, file), parent_dir)
                # Convert to module name: e.g. src.CoreFunctions.StateGraph.Workers.GmailWorker.worker
                module_name = os.path.splitext(rel_path)[0].replace(os.sep, ".")
                try:
                    importlib.import_module(module_name)
                except Exception as e:
                    print(f"⚠️ Error dynamically importing worker module '{module_name}': {e}")
