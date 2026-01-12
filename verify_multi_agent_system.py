import sys
import os
import warnings
warnings.filterwarnings("ignore")


# Ensure we can find src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from CoreFunctions.multi_agent.standard_agents import create_default_agency

def verify_multi_agent():
    print("[INFO] Verifying Multi-Agent System...")
    
    try:
        agency = create_default_agency()
        print("[SUCCESS] Agency Initialized Successfully.")
        print(f"Registered Agents: {list(agency.agents.keys())}")
        
        # Test 1: Simple Route to General Agent
        print("\n--- Test 1: General Query ---")
        response = agency.process_request("What is the capital of France?")
        print(f"Output: {response}")
        
        # Test 2: Route to WhatsApp Agent
        print("\n--- Test 2: WhatsApp Query (Mock) ---")
        # Note: This won't actually send unless WAHA is running, but it tests the routing
        response = agency.process_request("Check if WhatsApp is connected.")
        print(f"Output: {response}")

        # Test 3: Multi-Step Plan (Mock)
        # This is harder to mock without side effects, but we can see the plan generation logs in the output.
        print("\n--- Test 3: Complex Query ---")
        # "Get the weather in Agra and send it to me on WhatsApp"
        # This requires: Get Weather -> Send WhatsApp
        response = agency.process_request("Get the weather in Agra and then send the result to me on WhatsApp.")
        print(f"Output: {response}")

    except Exception as e:
        print("[ERROR] Verification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("DEBUG: Script started", file=sys.stderr)
    verify_multi_agent()
    print("DEBUG: Script finished", file=sys.stderr)
