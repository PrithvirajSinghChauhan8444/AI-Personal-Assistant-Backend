import os
import json
import tempfile
import pytest
from src.CoreFunctions.StateGraph.executor import resolve_file_references, _clean_working_memory_for_worker

def test_resolve_file_references():
    # Create temporary files mimicking session cache files
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump({"data": "hello world", "nested": [1, 2, 3]}, f)
        temp_json_path = f.name
        
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("plain text content")
        temp_txt_path = f.name

    try:
        # Build structure with references
        data = {
            "task_1": {
                "__file_reference__": temp_json_path,
                "size_bytes": 100,
                "preview": "..."
            },
            "task_2": {
                "__file_reference__": temp_txt_path,
                "size_bytes": 50,
                "preview": "..."
            },
            "other_field": "keep_this"
        }
        
        resolved = resolve_file_references(data)
        
        # JSON should be parsed back to structure
        assert resolved["task_1"] == {"data": "hello world", "nested": [1, 2, 3]}
        # Plain text should be read as raw string
        assert resolved["task_2"] == "plain text content"
        # Other fields remain untouched
        assert resolved["other_field"] == "keep_this"
        
    finally:
        if os.path.exists(temp_json_path):
            os.remove(temp_json_path)
        if os.path.exists(temp_txt_path):
            os.remove(temp_txt_path)

def test_clean_working_memory_resolves_references():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump({"test": "yes"}, f)
        temp_path = f.name
        
    try:
        working_memory = {
            "task_1": {
                "__file_reference__": temp_path,
                "size_bytes": 50,
                "preview": "..."
            },
            "user_profile": {"name": "Test User"}
        }
        
        cleaned = _clean_working_memory_for_worker(working_memory, depends_on=["task_1"])
        
        assert "task_1" in cleaned
        assert cleaned["task_1"] == {"test": "yes"}
        assert "user_profile" in cleaned
        assert cleaned["user_profile"] == {"name": "Test User"}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
