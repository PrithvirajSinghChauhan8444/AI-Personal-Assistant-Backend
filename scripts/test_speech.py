import sys
import os

# Add project root to path to resolve imports properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

TEST_SENTENCE = (
    "Hello! This is a voice test. Today is August 18, 2026, and the current level is 99.5%. "
    "Can you hear me clearly, or is the pitch and speed off? Let's count: 1, 2, 3, 4, 5."
)

def main():
    print("============================================================")
    print("                TTS Configuration Tester                     ")
    print("============================================================")
    print("Instructions:")
    print("1. Modify the values in config/speech_config.json directly.")
    print("2. Press ENTER in this console to load the updated JSON config and play.")
    print("3. Type 'q' or 'exit' and press ENTER to quit.")
    print("============================================================")
    
    from src.CoreFunctions.Integrations.Automation import scheduler_ops
    
    while True:
        # Load the configuration directly from the JSON config loader
        config = scheduler_ops.load_speech_config()
        
        print("\nLoaded Configuration:")
        for key, val in config.items():
            print(f"  {key}: {val}")
        
        print("\nSpeaking: \"" + TEST_SENTENCE + "\"")
        scheduler_ops.speak_text(TEST_SENTENCE)
        
        user_input = input("\n[Press ENTER to reload JSON & speak again, or 'q' to quit]: ").strip().lower()
        if user_input in ['q', 'exit', 'quit']:
            print("Exiting TTS Tester. Goodbye!")
            break

if __name__ == '__main__':
    main()
