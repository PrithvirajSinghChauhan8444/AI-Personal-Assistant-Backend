import google.generativeai as genai
import os
from dotenv import load_dotenv

# 1. Load your API Key
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("Searching for available models...\n")

try:
    # 2. List all models available to your key
    for m in genai.list_models():
        # 3. Only show models that support "generateContent" (Chat)
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
            
except Exception as e:
    print(f"Error: {e}")
    print("\nTroubleshooting:")
    print("1. Check if your .env file exists and has GEMINI_API_KEY=...")
    print("2. Check if your API key is active in Google AI Studio.")