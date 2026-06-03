import os
import sys

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))) # Add root for src.X imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))     # Add src/ for CoreFunctions imports


from src.CoreFunctions.security_utils import is_path_safe, is_command_safe, is_extension_safe
from src.Apps.FileOperations.file_manager import write_file, read_file
from src.Apps.SystemControl.execution import run_terminal_command, run_python_script
from src.CoreFunctions.file_vector_store import index_file, search_files_semantically, rag_qa_file

def run_tests():
    print("🧪 Starting Sandbox Security & RAG Pipeline Tests...")
    
    # Get workspace base dir
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(f"Workspace root: {base_dir}")
    
    # -------------------------------------------------------------
    # Test 1: Path Sandboxing (security_utils)
    # -------------------------------------------------------------
    print("\n--- Test 1: Path Sandboxing Checks ---")
    safe_path_1 = os.path.join(base_dir, "Memory", "test.json")
    safe_path_2 = os.path.join("/home/prit/Documents/Obsidian Vaultt", "Logs", "daily.md")
    unsafe_path_1 = "/etc/passwd"
    unsafe_path_2 = "/home/prit/.ssh/id_rsa"
    unsafe_path_3 = os.path.join(base_dir, "..", "escape_workspace.txt")
    
    print(f"is_path_safe('{safe_path_1}'): {is_path_safe(safe_path_1)} (Expected: True)")
    print(f"is_path_safe('{safe_path_2}'): {is_path_safe(safe_path_2)} (Expected: True)")
    print(f"is_path_safe('{unsafe_path_1}'): {is_path_safe(unsafe_path_1)} (Expected: False)")
    print(f"is_path_safe('{unsafe_path_2}'): {is_path_safe(unsafe_path_2)} (Expected: False)")
    print(f"is_path_safe('{unsafe_path_3}'): {is_path_safe(unsafe_path_3)} (Expected: False)")
    
    # -------------------------------------------------------------
    # Test 2: Extension Blocking
    # -------------------------------------------------------------
    print("\n--- Test 2: Extension Safety Checks ---")
    print(f"is_extension_safe('test.txt'): {is_extension_safe('test.txt')} (Expected: True)")
    print(f"is_extension_safe('test.py'): {is_extension_safe('test.py')} (Expected: True)")
    print(f"is_extension_safe('test.sh'): {is_extension_safe('test.sh')} (Expected: False)")
    print(f"is_extension_safe('test.exe'): {is_extension_safe('test.exe')} (Expected: False)")
    
    # -------------------------------------------------------------
    # Test 3: Command Filtering
    # -------------------------------------------------------------
    print("\n--- Test 3: Command Safety Checks ---")
    print(f"is_command_safe('ls -la'): {is_command_safe('ls -la')} (Expected: True)")
    print(f"is_command_safe('echo hello'): {is_command_safe('echo hello')} (Expected: True)")
    print(f"is_command_safe('sudo apt update'): {is_command_safe('sudo apt update')} (Expected: False)")
    print(f"is_command_safe('rm -rf /'): {is_command_safe('rm -rf /')} (Expected: False)")
    
    # -------------------------------------------------------------
    # Test 4: FileManager Protection
    # -------------------------------------------------------------
    print("\n--- Test 4: FileManager Safe Operations ---")
    write_res_safe = write_file(safe_path_1, "test content")
    print(f"write_file(safe_path_1): {write_res_safe}")
    
    write_res_unsafe = write_file(unsafe_path_1, "malicious content")
    print(f"write_file(unsafe_path_1): {write_res_unsafe}")
    
    read_res_safe = read_file(safe_path_1)
    print(f"read_file(safe_path_1): {read_res_safe}")
    
    read_res_unsafe = read_file(unsafe_path_1)
    print(f"read_file(unsafe_path_1): {read_res_unsafe}")
    
    # Clean up safe test file
    if os.path.exists(safe_path_1):
        os.remove(safe_path_1)
        
    # -------------------------------------------------------------
    # Test 5: Command/Script Exec Protection
    # -------------------------------------------------------------
    print("\n--- Test 5: Execution Safety checks ---")
    cmd_res_safe = run_terminal_command("echo 'Sandbox is active!'")
    print(f"run_terminal_command('echo...'): {cmd_res_safe.strip()}")
    
    cmd_res_unsafe = run_terminal_command("sudo rm -rf /tmp/some_fake_file")
    print(f"run_terminal_command('sudo rm...'): {cmd_res_unsafe.strip()}")
    
    py_res_unsafe = run_python_script(unsafe_path_1)
    print(f"run_python_script('/etc/passwd'): {py_res_unsafe.strip()}")

    # -------------------------------------------------------------
    # Test 6: Document RAG & Vector Indexing Pipeline
    # -------------------------------------------------------------
    print("\n--- Test 6: Vector DB & RAG Pipeline ---")
    temp_rag_file = os.path.join(base_dir, "Memory", "rag_test_doc.txt")
    doc_content = """
    Project Codename: Aetherium
    Lead Developer: Prithviraj
    Status: Experimental Alpha Phase.
    The primary database used by this system is PostgresQL.
    The secret access code is AETHER-9941.
    """
    write_file(temp_rag_file, doc_content)
    
    # Index the file
    print("Indexing test document...")
    index_res = index_file(temp_rag_file)
    print(index_res)
    
    # Semantic Search
    print("\nQuerying: 'What database is used?'")
    search_res = search_files_semantically("What database is used?", k=1)
    print(search_res)
    
    # RAG QA on file
    print("\nRunning RAG QA: 'What is the secret access code?'")
    qa_res = rag_qa_file("What is the secret access code?", temp_rag_file)
    print(qa_res)
    
    # Clean up test file
    if os.path.exists(temp_rag_file):
        os.remove(temp_rag_file)
        
    print("\n✅ Sandbox Security & RAG Pipeline testing completed.")

if __name__ == "__main__":
    run_tests()
