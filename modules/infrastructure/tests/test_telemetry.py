import unittest
import os
import tempfile
import json
from modules.infrastructure.observability.telemetry import TelemetryManager, get_module_tracer

class TestOpenTelemetryIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.traces_file = os.path.join(self.temp_dir.name, "test_otel_spans.jsonl")
        # Reset telemetry manager singleton state for test isolation
        TelemetryManager._initialized = False
        TelemetryManager.initialize(
            service_name="test-service",
            traces_file=self.traces_file,
            export_to_console=False
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_span_creation_and_file_export(self):
        tracer = get_module_tracer("test_module")
        with tracer.start_as_current_span("test.operation") as span:
            span.set_attribute("test.key", "test_value")
            span.set_attribute("test.count", 42)

        self.assertTrue(os.path.exists(self.traces_file))
        with open(self.traces_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertTrue(len(lines) >= 1)
            last_span = json.loads(lines[-1])
            self.assertEqual(last_span["name"], "test.operation")
            self.assertEqual(last_span["attributes"]["test.key"], "test_value")
            self.assertEqual(last_span["attributes"]["test.count"], 42)
            self.assertIn("trace_id", last_span["context"])
            self.assertIn("span_id", last_span["context"])

if __name__ == "__main__":
    unittest.main()
