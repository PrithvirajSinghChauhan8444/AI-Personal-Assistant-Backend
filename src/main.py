import os
import sys
from dotenv import load_dotenv

# Ensure core modules can be found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from CoreFunctions.path_utils import get_config_path
from CoreFunctions.multi_agent import create_default_agency

# ✅ Load .env from config/
load_dotenv(get_config_path(".env"))

def main():
    print("🤖 AI Personal Assistant (Multi-Agent) — Gemini 2.5 Flash")
    print("Initialize Agency...")
    try:
        agency = create_default_agency()
        print("✅ Agency Ready. Agents: ", list(agency.agents.keys()))
        print("Type 'exit' to quit.\n")
    except Exception as e:
        print(f"❌ Failed to initialize agency: {e}")
        return

    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ["exit", "quit"]:
                print("👋 Goodbye!")
                break
            
            if not user_input:
                continue

            # Route everything through the Multi-Agent Orchestrator
            response = agency.process_request(user_input)
            
            print(f"Assistant: {response}\n")

        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")

if __name__ == "__main__":
    main()
