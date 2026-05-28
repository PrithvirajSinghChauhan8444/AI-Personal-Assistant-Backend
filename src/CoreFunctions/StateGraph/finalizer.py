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

def output_finalizer_node(state: AgentState):
    print("\n[Node: Output Finalizer] Synthesizing final response...")
    primary_goal = state.get("primary_goal", "")
    completed_tasks = state.get("completed_tasks", {})
    
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.7)
    
    logs_str = json.dumps(completed_tasks, indent=2)
    
    content = f"User Request: {primary_goal}\n\nExecution Logs:\n{logs_str}"
    
    print("\n\033[1;35m🤖 Assistant:\033[0m ", end="", flush=True)
    
    full_response = ""
    try:
        for chunk in llm.stream([
            SystemMessage(content=FINALIZER_PROMPT),
            HumanMessage(content=content)
        ]):
            if chunk.content:
                full_response += chunk.content
                print(chunk.content, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"\n❌ Error during streaming: {e}")
        # Fallback to invoke if stream fails
        result = llm.invoke([
            SystemMessage(content=FINALIZER_PROMPT),
            HumanMessage(content=content)
        ])
        full_response = result.content
        print(full_response)
        print()
    
    return {
        "final_response": full_response
    }
