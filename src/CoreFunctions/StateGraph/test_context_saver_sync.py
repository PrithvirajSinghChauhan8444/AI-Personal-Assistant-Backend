import os
import sys
import json

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from dotenv import load_dotenv
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', '.env')), override=True)

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

chat_history = [
    {"role": "user", "content": "hello"},
    {"role": "assistant", "content": "hi there!"}
]
working_memory = {
    "previous_session_summary": "Initial summary"
}
completed_tasks = {}

transient_keys = ["active_skills", "skills_index", "user_profile", "relevant_memories", "fast_path_matched"]
filtered_wm = {k: v for k, v in working_memory.items() if k not in transient_keys}

context_data = {
    "chat_history": chat_history,
    "working_memory": filtered_wm,
    "completed_tasks": completed_tasks,
    "session_summary": working_memory.get("previous_session_summary", "")
}

print("Instantiating ChatGoogleGenerativeAI...")
llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0)
summary_prompt = """
You are a context saver. Summarize the user's goals and what actions the assistant completed in this session in 2-3 concise sentences.
Focus on outcomes: what files were created, what decisions were made, and what data was retrieved.
Do not include system instructions or formatting tags. Keep it plain text.
"""

history_str = ""
for msg in chat_history[-6:]:
    history_str += f"{msg['role']}: {msg['content']}\n"

print(f"History string:\n{history_str}")

print("Invoking LLM...")
response = llm.invoke([
    SystemMessage(content=summary_prompt),
    HumanMessage(content=f"History of recent turns:\n{history_str}")
])

print(f"Response: {response}")
print(f"Response type: {type(response)}")
print(f"Response content: {response.content}")
print(f"Response content type: {type(response.content)}")

content = response.content
if isinstance(content, list):
    print("Content is list.")
    text_parts = []
    for item in content:
        print(f"Item: {item}, type: {type(item)}")
        if isinstance(item, dict) and "text" in item:
            text_parts.append(item["text"])
        elif isinstance(item, str):
            text_parts.append(item)
    summary_text = "".join(text_parts).strip()
else:
    print("Content is not list.")
    summary_text = str(content).strip()

print(f"Summary text: {summary_text}")
