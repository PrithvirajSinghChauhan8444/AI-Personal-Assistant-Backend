import os
import json
import threading
from typing import Optional, Dict, Any, Generator
from contextlib import contextmanager

# Check if OpenTelemetry is available
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode, Span
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter, SpanExportResult
    from opentelemetry.sdk.resources import Resource
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    trace = None
    Span = None

class FileSpanExporter(SpanExporter if OPENTELEMETRY_AVAILABLE else object):
    """Exports OpenTelemetry spans as JSON lines to a local log file."""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

    def export(self, spans) -> Any:
        with self._lock:
            try:
                with open(self.file_path, "a", encoding="utf-8") as f:
                    for span in spans:
                        span_dict = {
                            "name": span.name,
                            "context": {
                                "trace_id": format(span.context.trace_id, "032x"),
                                "span_id": format(span.context.span_id, "016x"),
                                "trace_state": str(span.context.trace_state)
                            },
                            "parent_id": format(span.parent.span_id, "016x") if span.parent else None,
                            "start_time": span.start_time,
                            "end_time": span.end_time,
                            "duration_ns": span.end_time - span.start_time if span.end_time and span.start_time else 0,
                            "status": {
                                "status_code": str(span.status.status_code),
                                "description": span.status.description
                            },
                            "attributes": dict(span.attributes) if span.attributes else {},
                            "events": [
                                {
                                    "name": event.name,
                                    "timestamp": event.timestamp,
                                    "attributes": dict(event.attributes) if event.attributes else {}
                                }
                                for event in span.events
                            ]
                        }
                        f.write(json.dumps(span_dict) + "\n")
                return SpanExportResult.SUCCESS if OPENTELEMETRY_AVAILABLE else None
            except Exception as e:
                return SpanExportResult.FAILURE if OPENTELEMETRY_AVAILABLE else None

    def shutdown(self):
        pass

class TelemetryManager:
    """Configures and manages OpenTelemetry TracerProvider across all modules."""
    _initialized = False
    _lock = threading.Lock()
    _provider = None

    @classmethod
    def initialize(
        cls,
        service_name: str = "ai-personal-assistant",
        traces_file: Optional[str] = None,
        export_to_console: bool = False
    ):
        with cls._lock:
            if not OPENTELEMETRY_AVAILABLE:
                return
            
            if not traces_file:
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                traces_file = os.path.join(project_root, "Memory", "logs", "otel_traces.jsonl")

            current_provider = trace.get_tracer_provider()
            if isinstance(current_provider, TracerProvider):
                provider = current_provider
            else:
                resource = Resource.create({"service.name": service_name, "service.version": "2.0.0"})
                provider = TracerProvider(resource=resource)
                try:
                    trace.set_tracer_provider(provider)
                except Exception:
                    pass

            # Local file JSON span exporter for trace persistence
            file_exporter = FileSpanExporter(traces_file)
            provider.add_span_processor(SimpleSpanProcessor(file_exporter))

            # Optional console exporter
            if export_to_console:
                from opentelemetry.sdk.trace.export import ConsoleSpanExporter
                provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

            cls._provider = provider
            cls._initialized = True


    @classmethod
    def get_tracer(cls, module_name: str):
        if not cls._initialized:
            cls.initialize()
        if OPENTELEMETRY_AVAILABLE:
            return trace.get_tracer(module_name)
        return NoOpTracer()

class NoOpSpan:
    """Fallback span when OpenTelemetry is unavailable."""
    def set_attribute(self, key: str, value: Any):
        pass
    def set_attributes(self, attributes: Dict[str, Any]):
        pass
    def set_status(self, status: Any, description: Optional[str] = None):
        pass
    def record_exception(self, exception: Exception):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class NoOpTracer:
    """Fallback tracer when OpenTelemetry is unavailable."""
    @contextmanager
    def start_as_current_span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[NoOpSpan, None, None]:
        yield NoOpSpan()

def get_module_tracer(module_name: str):
    """Public helper to get a tracer for any module."""
    return TelemetryManager.get_tracer(module_name)
