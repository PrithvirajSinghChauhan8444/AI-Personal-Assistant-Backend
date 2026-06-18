import os
import sys
import unittest
from typing import List

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.StateGraph.registry import BaseWorker, WorkerRegistry

class TestWorkerRegistry(unittest.TestCase):
    def setUp(self):
        # Backup original registry and config to ensure isolation
        self.original_registry = dict(WorkerRegistry._registry)
        self.original_config = dict(WorkerRegistry._config)
        self.original_load_and_sync = WorkerRegistry.load_and_sync_config
        
        # Start each test with a clean registry
        WorkerRegistry._registry = {}
        WorkerRegistry._config = {}

        # Mock load_and_sync_config to sync in-memory only without touching the filesystem
        def mock_load_and_sync():
            for name, worker in WorkerRegistry._registry.items():
                if name not in WorkerRegistry._config:
                    default_model = "gemma4:e4b" if worker.use_local_llm else "gemini-3.1-flash-lite"
                    WorkerRegistry._config[name] = {
                        "model": default_model,
                        "active": True
                    }
        WorkerRegistry.load_and_sync_config = mock_load_and_sync

    def tearDown(self):
        # Restore backup
        WorkerRegistry._registry = self.original_registry
        WorkerRegistry._config = self.original_config
        WorkerRegistry.load_and_sync_config = self.original_load_and_sync

    def test_base_worker_cannot_be_instantiated(self):
        # Verify BaseWorker is abstract and cannot be instantiated directly
        with self.assertRaises(TypeError):
            BaseWorker()

    def test_registration_success(self):
        # Define a valid subclass of BaseWorker
        @WorkerRegistry.register
        class DummyValidWorker(BaseWorker):
            name = "DummyValidWorker"
            description = "A dummy worker for testing."
            instructions = "Do nothing."
            tools = []
            categories = ["testing"]

        # Verify it was successfully registered
        self.assertIn("DummyValidWorker", WorkerRegistry._registry)
        self.assertIsInstance(WorkerRegistry._registry["DummyValidWorker"], DummyValidWorker)
        
        # Verify retrieval functions
        self.assertEqual(WorkerRegistry.get_worker_names(), ["DummyValidWorker"])
        self.assertEqual(WorkerRegistry.get_worker("DummyValidWorker").name, "DummyValidWorker")

    def test_registration_fails_non_subclass(self):
        # Trying to register a class that doesn't inherit from BaseWorker
        with self.assertRaises(TypeError) as context:
            @WorkerRegistry.register
            class NotAWorker:
                pass
        self.assertIn("must inherit from BaseWorker", str(context.exception))

    def test_registration_fails_missing_abstract_properties(self):
        # Subclass missing required properties (abstract methods/properties)
        with self.assertRaises(TypeError) as context:
            @WorkerRegistry.register
            class MissingPropertiesWorker(BaseWorker):
                # Missing name, description, instructions, tools, categories properties
                pass
        self.assertIn("Failed to instantiate", str(context.exception))

    def test_get_worker_raises_key_error_for_inactive_or_missing(self):
        # Verify get_worker raises KeyError when requested worker doesn't exist
        with self.assertRaises(KeyError):
            WorkerRegistry.get_worker("NonExistentWorker")

    def test_get_all_workers_filters_active(self):
        # Register active and inactive dummy workers
        @WorkerRegistry.register
        class ActiveWorker(BaseWorker):
            name = "ActiveWorker"
            description = "Active"
            instructions = "Active"
            tools = []
            categories = ["test"]

        @WorkerRegistry.register
        class InactiveWorker(BaseWorker):
            name = "InactiveWorker"
            description = "Inactive"
            instructions = "Inactive"
            tools = []
            categories = ["test"]

        # Inject config directly to mock the configuration loaded state
        WorkerRegistry._config = {
            "ActiveWorker": {"active": True},
            "InactiveWorker": {"active": False}
        }

        # Check get_all_workers behaves correctly
        all_workers = WorkerRegistry.get_all_workers()
        self.assertIn("ActiveWorker", all_workers)
        self.assertNotIn("InactiveWorker", all_workers)

        # Check get_worker_names handles inactive correctly
        names = WorkerRegistry.get_worker_names()
        self.assertEqual(names, ["ActiveWorker"])

        # Check get_worker raises KeyError for the inactive worker
        with self.assertRaises(KeyError):
            WorkerRegistry.get_worker("InactiveWorker")

    def test_scan_and_register_workers_registers_active_workers(self):
        from src.CoreFunctions.StateGraph.registry import scan_and_register_workers
        
        # Set up a test configuration where only a subset of workers are active
        test_config = {
            "SystemWorker": {"model": "gemini-3.1-flash-lite", "active": True},
            "GmailWorker": {"model": "gemini-3.1-flash-lite", "active": True},
            "MemoryWorker": {"model": "gemma4:e4b", "active": False}
        }
        
        # Directly mock the config so that register filters based on this
        WorkerRegistry._config = test_config
        
        # Mock load_and_sync_config to preserve our test config
        def mock_load_and_sync():
            WorkerRegistry._config = test_config
        WorkerRegistry.load_and_sync_config = mock_load_and_sync

        # Clear cached modules from sys.modules to force re-execution of registration decorators
        for module_name in list(sys.modules.keys()):
            if "StateGraph.Workers" in module_name:
                del sys.modules[module_name]

        # Run the scan and register function
        scan_and_register_workers()
        
        # Verify that SystemWorker and GmailWorker are registered, but MemoryWorker is not
        registered_names = set(WorkerRegistry._registry.keys())
        self.assertIn("SystemWorker", registered_names)
        self.assertIn("GmailWorker", registered_names)
        self.assertNotIn("MemoryWorker", registered_names)

    def test_router_prompt_generation_with_active_workers(self):
        from src.CoreFunctions.StateGraph.task_router import get_router_prompt
        
        # Register dummy graph-node workers
        @WorkerRegistry.register
        class TestActiveWorker(BaseWorker):
            name = "TestActiveWorker"
            description = "Handles active tasks."
            instructions = "Active"
            tools = []
            categories = ["test"]
            is_graph_node = True

        @WorkerRegistry.register
        class TestInactiveWorker(BaseWorker):
            name = "TestInactiveWorker"
            description = "Handles inactive tasks."
            instructions = "Inactive"
            tools = []
            categories = ["test"]
            is_graph_node = True

        @WorkerRegistry.register
        class TestSubWorker(BaseWorker):
            name = "TestSubWorker"
            description = "Sub worker not exposed to router."
            instructions = "Sub"
            tools = []
            categories = ["test"]
            is_graph_node = False

        # Set config state
        WorkerRegistry._config = {
            "TestActiveWorker": {"active": True},
            "TestInactiveWorker": {"active": False},
            "TestSubWorker": {"active": True}
        }

        # Generate the prompt
        prompt = get_router_prompt()
        
        # Check active graph node worker is listed
        self.assertIn("- TestActiveWorker: Handles active tasks.", prompt)
        
        # Check inactive worker and sub-worker are NOT listed
        self.assertNotIn("TestInactiveWorker", prompt)
        self.assertNotIn("TestSubWorker", prompt)


if __name__ == "__main__":
    unittest.main()
