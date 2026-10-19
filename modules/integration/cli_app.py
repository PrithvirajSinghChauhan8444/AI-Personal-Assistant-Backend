import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from modules.integration.application_orchestrator import ApplicationOrchestrator

def main():
    print("🤖 ===================================================")
    print("   AI Personal Assistant (Decoupled Modular Architecture)")
    print("======================================================")
    print("Type 'exit' or 'quit' to stop.\n")

    orchestrator = ApplicationOrchestrator()

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("👋 Goodbye!")
                break

            response = orchestrator.run(user_input)
            print(f"\nAssistant: {response}")

        except (KeyboardInterrupt, EOFError):
            print("\n👋 Session ended.")
            break

if __name__ == "__main__":
    main()
