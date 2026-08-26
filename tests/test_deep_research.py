import sys
import os
import glob

# Ensure src path is in Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.SharedTools.deep_research import deep_research

def test_recursive_deep_research():
    print("🔬 Running Integration Test for Recursive Deep Research...")
    
    topic = "Playwright testing library features"
    
    # We run with max_depth=2 to test query expansion + recursive loop + synthesis
    # without taking too much time/API cost.
    report = deep_research(topic=topic, max_depth=2)
    
    print("\n🔍 Verification of Output Report:")
    print(f"  Report length: {len(report)} characters")
    print(f"  Report preview (first 500 chars):\n{report[:500]}")
    
    # Check that report is returned and contains expected structure
    assert report is not None
    assert "Deep Research Completed!" in report
    assert "Playwright" in report
    assert "Sources & References" in report or "References" in report
    
    # Check that report was saved to the files
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    reports_dir = os.path.join(project_root, "Memory", "research_reports")
    assert os.path.exists(reports_dir), f"Reports folder '{reports_dir}' was not created!"
    
    matching_files = glob.glob(os.path.join(reports_dir, "research_Playwright_*.md"))
    matching_files = sorted(matching_files, key=os.path.getmtime, reverse=True)
    print(f"  Found matching saved files (newest first): {matching_files}")
    assert len(matching_files) > 0, "No research report file was saved!"
    
    # Verify file content
    saved_file_path = matching_files[0]
    with open(saved_file_path, "r", encoding="utf-8") as f:
        file_content = f.read()
    assert "Playwright" in file_content, "Saved report content is missing the topic keyword!"
    
    print(f"  ✅ Saved report file verified successfully at: {saved_file_path}")
    print("  ✅ Recursive Deep Research loop integration test passed.")

if __name__ == "__main__":
    test_recursive_deep_research()
