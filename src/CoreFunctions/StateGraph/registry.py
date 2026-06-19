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
    def enable_prompt_caching(self) -> bool:
        """Flag to enable Gemini prompt context caching (only works with Gemini models)."""
        return False

    @property
    def is_graph_node(self) -> bool:
        """Whether this worker should be exposed as a top-level node in the main LangGraph and router."""
        return True

    @property
    def routing_rules(self) -> List[str]:
        """Rules or workflows specific to this worker that should be added to the TaskRouter prompt."""
        return []

    def execute(self, state: AgentState) -> dict:
        """Execution node function added to the LangGraph."""
        # Import dynamically to prevent circular imports
        from src.CoreFunctions.StateGraph.executor import _execute_worker_node
        return _execute_worker_node(state, self.name)

class WorkerRegistry:
    _registry: Dict[str, BaseWorker] = {}
    _config: Dict[str, dict] = {}

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
        
        # Load config if not loaded yet
        if not cls._config:
            cls.load_and_sync_config()
            
        # Only register if active
        if cls._config.get(worker_instance.name, {}).get("active", True):
            cls._registry[worker_instance.name] = worker_instance
            
        return worker_cls

    @classmethod
    def load_and_sync_config(cls):
        import json
        # Find root dir
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        config_dir = os.path.join(root_dir, "config")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "workers_config.json")
        
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception as e:
                print(f"⚠️ Error reading workers_config.json: {e}")
                
        updated = False
        # Sync with currently registered workers
        for name, worker in list(cls._registry.items()):
            if name not in config:
                default_model = "gemma4:e4b" if worker.use_local_llm else "gemini-3.1-flash-lite"
                config[name] = {
                    "model": default_model,
                    "active": True
                }
                updated = True
                
        if updated or not os.path.exists(config_path):
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4)
            except Exception as e:
                print(f"⚠️ Error writing workers_config.json: {e}")
                
        cls._config = config

    @classmethod
    def get_all_workers(cls) -> Dict[str, BaseWorker]:
        """Returns the dictionary of registered active worker instances."""
        cls.load_and_sync_config()
        active_workers = {}
        for name, worker in cls._registry.items():
            if cls._config.get(name, {}).get("active", True):
                active_workers[name] = worker
        return active_workers

    @classmethod
    def get_worker_names(cls) -> List[str]:
        """Returns a sorted list of registered active worker names."""
        return sorted(list(cls.get_all_workers().keys()))

    @classmethod
    def get_worker(cls, name: str) -> BaseWorker:
        """Retrieves a registered active worker instance by name."""
        workers = cls.get_all_workers()
        if name not in workers:
            raise KeyError(f"Worker '{name}' is not registered or is currently inactive.")
        return workers[name]

def scan_and_register_workers(workers_dir: str = None, force_reload: bool = False):
    """Dynamically walks and imports all python files inside the workers directory to trigger registration decorators."""
    if force_reload:
        # Clear registry and config
        WorkerRegistry._registry = {}
        WorkerRegistry._config = {}
        # Clear cached modules from sys.modules to force execution of registration decorators
        for module_name in list(sys.modules.keys()):
            if "StateGraph.Workers" in module_name:
                del sys.modules[module_name]

    if workers_dir is None:
        workers_dir = os.path.join(os.path.dirname(__file__), "Workers")
        
    if not os.path.exists(workers_dir):
        return
        
    # We want to add the parent of the src/ directory to path if not present
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(workers_dir)))) # Project root
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
        
    # Load / synchronize configuration first so register can filter active status correctly
    WorkerRegistry.load_and_sync_config()
        
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
