import os
import sys
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Optional, Any
from dotenv import load_dotenv

# Ensure we can find CoreFunctions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from CoreFunctions.tools import AVAILABLE_TOOLS

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

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
        self.functions = {} # Map function names to callables
        
        for tool_name in self.config.tools:
            if tool_name in AVAILABLE_TOOLS:
                func = AVAILABLE_TOOLS[tool_name]
                selected_tools.append(func)
                # Map the actual function name (as seen by Gemini) to the callable
                if hasattr(func, '__name__'):
                    self.functions[func.__name__] = func
                else:
                    self.functions[tool_name] = func # Fallback
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
        Handles tool calls automatically via the Gemini SDK with manual recursion.
        """
        print(f"\n[AGENT: {self.config.name}] Processing...")
        try:
            response = self._chat.send_message(message)
            return self._handle_response(response)
            
        except Exception as e:
            return f"[ERROR] in agent {self.config.name}: {e}"

    def _handle_response(self, response):
        """
        Recursively handles function calls until text is generated.
        """
        try:
            part = response.parts[0]
        except IndexError:
             return "Empty response."

        if fn := part.function_call:
            tool_name = fn.name
            # Convert MapComposite to dict
            total_args = {k: v for k, v in fn.args.items()}
            
            print(f"    [TOOL CALL] {tool_name}({total_args})")
            
            result = "Error: Tool not found"
            # Use the local function map which keys by function name
            if tool_name in self.functions:
                try:
                    func = self.functions[tool_name]
                    result = func(**total_args)
                except Exception as e:
                    result = f"Error executing {tool_name}: {e}"
            else:
                result = f"Error: Tool {tool_name} not found. Available: {list(self.functions.keys())}"
            
            print(f"    ↳ Result: {str(result)[:100]}...")
            
            # Send result back
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
