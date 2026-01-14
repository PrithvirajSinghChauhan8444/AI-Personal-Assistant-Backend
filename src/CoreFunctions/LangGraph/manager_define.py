from typing import List, Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel
import json

class ManagerAgent:
    """
    Constructs the Supervisor (Manager) Node.
    
    The manager does not execute tools itself. Instead, it:
    1. Reviews the conversation history.
    2. Decides which Worker should act next OR if the task is finished.
    3. Returns a routing decision.
    """
    
    def __init__(self, model, members: List[str], system_prompt: str):
        """
        Args:
            model: The LLM to Use (must support function calling/structured output).
            members: A list of worker names (e.g., ["GmailWorker", "CalendarWorker"]).
            system_prompt: High-level instructions for the manager.
        """
        self.model = model
        self.members = members
        self.system_prompt = system_prompt
        
        # 1. Define the Router Structure
        # We dynamically create the options based on members + FINISH
        options = ["FINISH"] + members
        
        from typing import Optional
        
        # This Pydantic model defines the output schema for the router
        class RouteResponse(BaseModel):
            next: Literal[tuple(options)]
            final_response: Optional[str] = None
        
        self.RouteResponse = RouteResponse
        
        # 2. Build the Prompt
        # The prompt injects the member names so the LLM knows who is available.
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system", 
                "Given the conversation above, who should act next? "
                "Or should we FINISH? Select one of: {options}\n\n"
                "If you select FINISH, you MUST provide a 'final_response' to the user."
            ),
        ]).partial(options=str(options), members=", ".join(members))

        # 3. Create the Chain
        # We use with_structured_output to force the LLM to return the RouteResponse schema
        self.chain = (
            self.prompt 
            | self.model.with_structured_output(RouteResponse)
        )

    def create_node(self):
        """
        Returns the node function for the graph.
        """
        def supervisor_node(state: dict):
            # Run the chain on the current state (message history)
            result = self.chain.invoke(state)
            
            # Return both routing and response data
            return {
                "next": result.next,
                "final_response": result.final_response
            }
            
        return supervisor_node
