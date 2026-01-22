import os
import sys
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from src.CoreFunctions.LangGraph.logger import GraphLogger

# Ensure we can import from sibling modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Load env from config/.env
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../config/.env'))
load_dotenv(config_path)

try:
    from langchain_groq import ChatGroq
except ImportError:
    print("❌ Critical: 'langchain_groq' not installed. Please install it.")
    ChatGroq = None

# Initialize LLM (Reuse configuration)
if ChatGroq:
    llm = ChatGroq(
        model="qwen/qwen3-32b", 
        temperature=0.7 # Slightly higher temperature for more natural conversation
    )
else:
    llm = None

def output_finaliser_node(state: dict):
    """
    Node to reformat the final response into a natural conversational tone.
    """
    if not llm:
        return {"final_response": "Error: LLM not initialized for output finaliser."}

    final_response = state.get("final_response", "")
    messages = state.get("messages", [])
    
    # Get the last user message for context
    last_user_message = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break
            
    # If there's no final response to format, just return custom message or pass through
    if not final_response:
        return {"final_response": "I'm not sure what to say, but I'm done with the task."}

    prompt = ChatPromptTemplate.from_messages([
        ("system", 
         "You are an AI assistant's communication layer. "
         "Your job is to take a raw technical or dry response and the user's last input, "
         "and rephrase the response to be friendly, conversational, and natural. "
         "Do not change the underlying meaning or facts. "
         "If the raw response is already good, just output it as is. "
         "Keep it concise but polite."
        ),
        ("human", "User Input: {user_input}\nRaw Response: {raw_response}")
    ])

    GraphLogger.log_node_start("Output Finaliser")
    
    chain = prompt | llm

    try:
        start_msg = f"User Input: {last_user_message}\nRaw Response: {final_response}"
        # We can just invoke with the dict inputs
        result = chain.invoke({"user_input": last_user_message, "raw_response": final_response})
        formatted_response = result.content
    except Exception as e:
        formatted_response = f"{final_response} (Formatting failed: {e})"

    GraphLogger.log_node_end("Output Finaliser")
    
    return {
        "final_response": formatted_response
    }
