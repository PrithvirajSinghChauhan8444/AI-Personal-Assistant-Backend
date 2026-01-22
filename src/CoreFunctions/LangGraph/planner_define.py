from typing import List
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel

class PlannerAgent:
    """
    Constructs the Planner Node.
    
    The planner:
    1. Receives the user's initial request.
    2. Analyses the request against available workers.
    3. Creates a step-by-step plan using the available workers.
    4. Adds the plan to the message history for the Manager to execute.
    """
    
    def __init__(self, model, members: List[str], system_prompt: str):
        """
        Args:
            model: The LLM to Use.
            members: A list of worker names.
            system_prompt: High-level instructions for the planner.
        """
        self.model = model
        self.members = members
        self.system_prompt = system_prompt
        
        # Build the Prompt
        # We now expect system_prompt to contain the worker info pre-formatted
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            MessagesPlaceholder(variable_name="messages"),
            (
                "human", 
                "Create a step-by-step plan to fulfill the user's request. "
                "The plan should be clear and concise. Do NOT execute the steps, just plan them."
            ),
        ]).partial(system_prompt=system_prompt)

        # Create the Chain
        self.chain = self.prompt | self.model

    def create_node(self):
        """
        Returns the node function for the graph.
        """
        from src.CoreFunctions.LangGraph.logger import GraphLogger

        def planner_node(state: dict):
            GraphLogger.log_node_start("Planner")
            
            # Run the chain on the current state (message history)
            result = self.chain.invoke(state)
            
            # The result is an AIMessage (or similar) containing the plan
            plan_content = result.content
            
            # We wrap it in a SystemMessage or AIMessage to distinguish it as a plan
            # Let's use AIMessage with a specific prefix so the Manager knows it's a plan
            formatted_plan = f"PLAN:\n{plan_content}"
            
            GraphLogger.log_node_end("Planner")
            
            return {
                "messages": [AIMessage(content=formatted_plan)]
            }
            
        return planner_node
