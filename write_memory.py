import sys
import os
from dotenv import load_dotenv

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Load .env
load_dotenv(override=True)

from src.CoreFunctions.memory import store_memory

def main():
    print("✍️  Direct Unified Memory Writer Helper")
    print("-" * 45)
    
    try:
        key = input("Enter memory key (e.g., dog_name): ").strip()
        if not key:
            print("❌ Error: Key cannot be empty.")
            return
            
        val = input("Enter memory value (e.g., Rusty): ").strip()
        if not val:
            print("❌ Error: Value cannot be empty.")
            return
            
        category = input("Enter category (user/past/current, default 'user'): ").strip() or "user"
        
        result = store_memory(category, key, val)
        print(f"\n✅ Success! {result}")
        print(f"👉 You can now run the assistant and ask: 'what is my {key}?'")
    except KeyboardInterrupt:
        print("\n👋 Cancelled.")
    except Exception as e:
        print(f"\n❌ Error writing to memory: {e}")

if __name__ == "__main__":
    main()
