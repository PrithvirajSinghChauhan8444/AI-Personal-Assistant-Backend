from typing import List, Any
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

class WorkerAgent:
    """
    A Factory class to create a Worker Agent Node for LangGraph.
    
    Each worker is a ReAct agent specialized with a specific set of tools
    and a specific system instructions.
    """
    
    def __init__(self, model, tools: List[StructuredTool], system_prompt: str):
        """
        Initialize the Worker Agent.

        Args:
            model: The LLM instance (e.g., ChatGoogleGenerativeAI, ChatOpenAI).
            tools: A list of LangChain StructuredTools available to this worker.
            system_prompt: The specific instructions for this worker.
        """
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        
        # Create the agent runnable using the prebuilt ReAct agent constructor
        # This handles the tool calling loop automatically.
        self.agent_runnable = create_react_agent(
            model, 
            tools, 
            prompt=system_prompt
        )

    def create_node(self):
        """
        Returns a function that can be used as a Node in the StateGraph.
        
        The node function receives the state, invokes the agent, 
        and returns the Update dict.
        """
        
        def worker_node(state: dict):
            """
            The actual node function executed by LangGraph.
            Input state is expected to have 'messages'.
            """
            # We pass the state directly to the prebuilt agent
            result = self.agent_runnable.invoke(state)
            
            # The result from create_react_agent is usually a dict with 'messages'
            # encompassing the chain of thought.
            
            # We return the new messages to append to the global state
            return {
                "messages": result["messages"]
            }
            
        return worker_node
