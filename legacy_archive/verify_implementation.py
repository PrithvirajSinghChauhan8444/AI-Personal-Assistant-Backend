
import sys
import os

# Create a mock .env for testing if needed, or rely on existing
# We just want to check if tools.py imports everything correctly without crashing

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

try:
    from CoreFunctions.tools import AVAILABLE_TOOLS
    print("✅ Successfully imported tools.py")
    
    expected_tools = [
        "write_file", "read_file", "list_files", "create_directory", "save_code",
        "run_cmd", "run_script", "launch_app"
    ]
    
    missing = []
    for tool in expected_tools:
        if tool in AVAILABLE_TOOLS:
            print(f"  - Found tool: {tool}")
        else:
            missing.append(tool)
            
    if missing:
        print(f"❌ Missing tools: {missing}")
        sys.exit(1)
    else:
        print("✅ All new tools registered successfully.")
        
except ImportError as e:
    print(f"❌ ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
