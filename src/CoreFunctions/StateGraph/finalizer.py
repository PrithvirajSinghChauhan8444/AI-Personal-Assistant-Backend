import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.CoreFunctions.StateGraph.state import AgentState

FINALIZER_PROMPT = """
You are the Output Finalizer. The system has completed a multi-step task for the user.
Below are the user's original request and the raw structured data from the completed tasks.
Synthesize this into a natural, friendly, and cohesive response to the user.
Do not mention "subtasks" or the internal architecture. Just provide the final answer or confirm the actions taken.
"""

from datetime import datetime

def output_finalizer_node(state: AgentState):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\nRunning Output Finaliser : ({timestamp})")
    
    # Check Fast-Path Bypass (Phase 2 Speed Optimization)
    working_memory = state.get("working_memory", {}) or {}
    if working_memory.get("fast_path_matched", False):
        final_resp = state.get("final_response", "")
        print(f"--- Output Finaliser Finished ---")
        print(f"\n📍 Node 'output_finaliser' Output:\n")
        print(f"💬 Manager says: ", end="", flush=True)
        
        # Stream character-by-character with a micro-delay for a premium, highly interactive terminal aesthetic
        import time
        for char in final_resp:
            print(char, end="", flush=True)
            time.sleep(0.008)
        print("\n")
        return {"final_response": final_resp}
        
    primary_goal = state.get("primary_goal", "")
    completed_tasks = state.get("completed_tasks", {}) or {}
    chat_history = state.get("chat_history", []) or []
    
    # Use high-speed cloud LLM for instant response synthesis and reliable execution
    llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.7)
    
    # 1. Format conversational history
    history_str = ""
    if chat_history:
        history_str = "Conversation History:\n"
        for msg in chat_history:
            history_str += f"- {msg['role'].capitalize()}: {msg['content']}\n"
            
    logs_str = json.dumps(completed_tasks, indent=2)
    
    content = ""
    if history_str:
        content += history_str + "\n"
    content += f"User Request: {primary_goal}\n\nExecution Logs:\n{logs_str}"
    
    print(f"--- Output Finaliser Finished ---")
    print(f"\n📍 Node 'output_finaliser' Output:\n")
    print(f"💬 Manager says: ", end="", flush=True)
    
    full_response = ""
    try:
        for chunk in llm.stream([
            SystemMessage(content=FINALIZER_PROMPT),
            HumanMessage(content=content)
        ]):
            if chunk.content:
                text_chunk = ""
                if isinstance(chunk.content, str):
                    text_chunk = chunk.content
                elif isinstance(chunk.content, list):
                    for item in chunk.content:
                        if isinstance(item, dict) and "text" in item:
                            text_chunk += item["text"]
                        elif isinstance(item, str):
                            text_chunk += item
                
                if text_chunk:
                    # Detect and handle cumulative streaming vs incremental streaming
                    if text_chunk.startswith(full_response) and len(text_chunk) > len(full_response):
                        new_text = text_chunk[len(full_response):]
                        full_response = text_chunk
                    else:
                        new_text = text_chunk
                        full_response += text_chunk
                    
                    print(new_text, end="", flush=True)
        print("\n")
    except Exception as e:
        # Fallback to invoke if stream fails
        result = llm.invoke([
            SystemMessage(content=FINALIZER_PROMPT),
            HumanMessage(content=content)
        ])
        if isinstance(result.content, str):
            full_response = result.content
        elif isinstance(result.content, list):
            text_parts = []
            for item in result.content:
                if isinstance(item, dict) and "text" in item:
                    text_parts.append(item["text"])
                elif isinstance(item, str):
                    text_parts.append(item)
            full_response = "".join(text_parts)
        else:
            full_response = str(result.content)
        print(full_response)
        print()
    
    return {
        "final_response": full_response
    }
