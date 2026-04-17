import os
from dotenv import load_dotenv
import google.generativeai as genai
from CoreFunctions.summarizer import summarize_text

# 1️⃣ Load environment variables from .env
load_dotenv()

# 2️⃣ Get the Gemini API key safely
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("❌ GEMINI_API_KEY not found in .env file!")

# 3️⃣ Configure the model
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.5-flash")

# 4️⃣ Main command handler
def handle_text_command(user_input: str):
    """
    Handles text-based commands like 'summarize', Q&A, etc.
    """
    try:
        return summarize_text(model, user_input)


    except Exception as e:
        return f"⚠️ Error while processing command: {e}"


user_input="d"
handle_text_command(model,user_input)