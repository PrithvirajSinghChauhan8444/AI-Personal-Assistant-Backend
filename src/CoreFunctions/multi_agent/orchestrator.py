import json
import google.generativeai as genai
from typing import Dict, List, Optional
from .base_agent import Agent

class AgentManager:
    """
    Manages multiple agents and orchestrates complex tasks.
    """
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        # The Orchestrator model plans the workflow
        self.planner_model = genai.GenerativeModel("gemini-2.0-flash-exp")

    def register_agent(self, agent: Agent):
        self.agents[agent.config.name] = agent

    def process_request(self, user_input: str) -> str:
        """
        Orchestrates the request by breaking it down into steps if necessary.
        """
        agent_info = {name: agent.config.system_instruction for name, agent in self.agents.items()}
        
        # 1. Planning Step
        prompt = f"""
        You are the Orchestrator. Breakdown the user request into a sequential list of steps.
        Each step must be assigned to ONE specific agent from the available list.
        
        User Request: "{user_input}"
        
        Available Agents & Capabilities:
        {json.dumps(agent_info, indent=2)}
        
        OUTPUT format (JSON ONLY):
        {{
            "plan": [
                {{ "agent": "AgentName", "instruction": "Clear instruction for the agent" }},
                ...
            ]
        }}
        
        Rules:
        - If the task is simple, use one step.
        - If the task requires information from Agent A to be sent by Agent B, create two steps.
        - Ensure the instruction for step 2 mentions using the result from step 1.
        - If the user asks for "Gmail" use the GmailAgent.
        - If the user asks for "WhatsApp" use the WhatsAppAgent.
        """
        
        print("\n[ORCHESTRATOR] Planning...")
        try:
            response = self.planner_model.generate_content(prompt)
            raw = response.text.replace("```json", "").replace("```", "").strip()
            # Clean up potentially messy JSON
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end != -1:
                raw = raw[start:end]
                
            plan_data = json.loads(raw)
            plan = plan_data.get("plan", [])
        except Exception as e:
            return f"Orchestration Planning Error: {e}"

        if not plan:
            return "Could not generate a valid plan."

        # 2. Execution Step
        context = ""
        final_response = ""
        
        for i, step in enumerate(plan, 1):
            agent_name = step.get("agent")
            instruction = step.get("instruction")
            
            if agent_name not in self.agents:
                print(f"⚠️ Unknown agent '{agent_name}', skipping step.")
                continue
                
            print(f"\n[Step {i}] assigning to {agent_name}...")
            print(f"   Instruction: {instruction}")
            
            # Append context from previous steps to the instruction
            if context:
                full_input = f"Context from previous steps:\n{context}\n\nTask: {instruction}"
            else:
                full_input = instruction
            
            result = self.agents[agent_name].process_message(full_input)
            
            # Update context
            context += f"\n[Step {i} Result ({agent_name})]: {result}"
            final_response = result # The last result is usually the answer to the user
            
            print(f"   [RESULT] {str(result)[:100]}...")

        return final_response
