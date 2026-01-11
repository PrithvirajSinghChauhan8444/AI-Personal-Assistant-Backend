
import os
import sys
import json
import inspect
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Optional, Any

import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content

from dotenv import load_dotenv

# Ensure we can find CoreFunctions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from CoreFunctions.tools import AVAILABLE_TOOLS
from CoreFunctions.memory import fetch_memory

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# ==========================================
# 1. AGENT DEFINITION
# ==========================================

@dataclass
class AgentConfig:
    name: str
    model_name: str
    system_instruction: str
    tools: List[str] = field(default_factory=list)
    temperature: float = 0.7

class Agent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.history = []
        self._model = self._setup_model()
        self._chat = self._model.start_chat(history=[])

    def _setup_model(self):
        # Filter available tools based on config
        selected_tools = []
        for tool_name in self.config.tools:
            if tool_name in AVAILABLE_TOOLS:
                selected_tools.append(AVAILABLE_TOOLS[tool_name])
            else:
                print(f"⚠️ Warning: Agent '{self.config.name}' requested missing tool '{tool_name}'")
        
        return genai.GenerativeModel(
            model_name=self.config.model_name,
            tools=selected_tools if selected_tools else None,
            system_instruction=self.config.system_instruction,
            generation_config=genai.types.GenerationConfig(
                temperature=self.config.temperature
            )
        )

    def process_message(self, message: str) -> str:
        """
        Sends a message to the agent and gets a response.
        Handles tool calls automatically via the Gemini SDK.
        """
        print(f"\n🤖 [{self.config.name}] Processing...")
        try:
            response = self._chat.send_message(message)
            return self._handle_response(response)
            
        except Exception as e:
            return f"❌ Error in agent {self.config.name}: {e}"

    def _handle_response(self, response):
        """
        recursively handles function calls until text is generated.
        """
        # The Gemini SDK 1.0+ handles automatic function calling IF configured, 
        # but manual handling gives us more control and visibility.
        # We check response.parts for function_call.
        
        try:
            part = response.parts[0]
        except IndexError:
             return "Empty response."

        if fn := part.function_call:
            tool_name = fn.name
            # Convert MapComposite to dict
            total_args = {k: v for k, v in fn.args.items()}
            
            print(f"    🛠️ Tool Call: {tool_name}({total_args})")
            
            result = "Error: Tool not found"
            if tool_name in AVAILABLE_TOOLS:
                try:
                    func = AVAILABLE_TOOLS[tool_name]
                    result = func(**total_args)
                except Exception as e:
                    result = f"Error executing {tool_name}: {e}"
            else:
                result = f"Error: Tool {tool_name} not found."
            
            print(f"    ↳ Result: {str(result)[:100]}...")
            
            # Send result back
            # We must construct a properly formatted FunctionResponse
            
            # Note: simplified for this implementation specific to Google GenAI SDK usage
            
            
            response_part = content.Part(
                function_response=content.FunctionResponse(
                    name=tool_name,
                    response={'result': result}
                )
            )
            
            # Continue the conversation
            next_response = self._chat.send_message(response_part)
            return self._handle_response(next_response)
        
        return response.text

# ==========================================
# 2. AGENT MANAGER (ROUTER)
# ==========================================


# ==========================================
# 2. AGENT MANAGER (ORCHESTRATOR)
# ==========================================

class AgentManager:
    """
    Manages multiple agents and orchestrates complex tasks.
    """
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        # The Orchestrator model plans the workflow
        self.planner_model = genai.GenerativeModel("gemma-3-12b-it") 

    def register_agent(self, agent: Agent):
        self.agents[agent.config.name] = agent

    def process_request(self, user_input: str) -> str:
        """
        Orchestrates the request by breaking it down into steps if necessary.
        """
        agent_list = list(self.agents.keys())
        agent_info = {name: agent.config.system_instruction for name, agent in self.agents.items()}
        
        # 1. Planning Step
        prompt = f"""
        You are the Orchestrator. breakdown the user request into a sequential list of steps.
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
        """
        
        print("\n🧠 Orchestrator Planning...")
        try:
            response = self.planner_model.generate_content(prompt)
            raw = response.text.replace("```json", "").replace("```", "").strip()
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
                
            print(f"\n🔄 [Step {i}] assigning to {agent_name}...")
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
            
            print(f"   ✅ Result: {str(result)[:100]}...")

        return final_response


# ==========================================
# 3. PREDEFINED AGENTS SETUP
# ==========================================

def create_default_agency() -> AgentManager:
    manager = AgentManager()

    # --- 1. General Assistant ---
    general_agent = Agent(AgentConfig(
        name="GeneralAssistant",
        model_name="gemma-3-12b-it", # Faster model for chit-chat
        system_instruction="You are a helpful AI assistant. Handle general queries, chit-chat, and simple questions. If a request is specific to coding, system operations, or communication, advise the user.",
        tools=["recall", "remember", "get_time", "get_weather"] 
    ))
    manager.register_agent(general_agent)

    # --- 2. Coder / System Admin ---
    coder_agent = Agent(AgentConfig(
        name="SystemEngineer",
        model_name="gemma-3-27b-it", # Stronger model for code
        system_instruction="You are a generic System Engineer. You can manage files, run commands, and write code. BE CAREFUL with system commands. Always verify safe operations.",
        tools=[
            "write_file", "read_file", "list_files", "create_directory", "save_code",
            "run_cmd", "run_script", "launch_app", "system_health"
        ]
    ))
    manager.register_agent(coder_agent)

    # --- 3. Communicator ---
    comm_agent = Agent(AgentConfig(
        name="Communicator",
        model_name="gemma-3-27b-it",
        system_instruction="You handle all communications (Email, WhatsApp) and Calendar scheduling. Be professional and concise.",
        tools=[
            "fetch_mails", "send_mail", "send_whatsapp", "whatsapp_status", 
            "find_contact", "read_whatsapp_messages", "add_task", 
            "check_events", "add_event"
        ]
    ))
    manager.register_agent(comm_agent)

    return manager

# ==========================================
# 4. ENTRY POINT (Testing)
# ==========================================

if __name__ == "__main__":
    print("🤖 Multi-Agent System Initializing...")
    agency = create_default_agency()
    
    print("✅ Agency Ready. Type 'exit' to quit.")
    while True:
        try:
            user_in = input("\nUser: ").strip()
            if user_in.lower() in ["exit", "quit"]:
                break
            
            if not user_in:
                continue

            response = agency.process_request(user_in)
            print(f"Agency: {response}")
            
        except KeyboardInterrupt:
            print("\nExiting.")
            break
