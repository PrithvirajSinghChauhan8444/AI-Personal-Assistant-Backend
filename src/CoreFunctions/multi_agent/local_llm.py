import inspect
import json
import ollama
from typing import List, Dict, Any, Optional

class LocalClient:
    """
    A client wrapper for the local Ollama instance.
    """
    def __init__(self, model_name: str, system_instruction: str = "", tools: List = None):
        self.model_name = model_name
        self.system_instruction = system_instruction
        self.tools = tools or []
        self.ollama_tools = [self._convert_to_ollama_tool(t) for t in self.tools] if self.tools else None
        self.history = []
        
        # Map function names to callables for execution
        self.function_map = {t.__name__: t for t in self.tools} if self.tools else {}

    def _convert_to_ollama_tool(self, func) -> Dict:
        """
        Converts a Python function to an Ollama tool schema.
        """
        signature = inspect.signature(func)
        docstring = inspect.getdoc(func) or "No description provided."
        
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for name, param in signature.parameters.items():
            param_type = "string" # Default
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == list:
                param_type = "array"
            elif param.annotation == dict:
                param_type = "object"
            
            parameters["properties"][name] = {
                "type": param_type,
                "description": f"Parameter {name}" # We could parse docstring for better desc
            }
            
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(name)
                
        return {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": docstring,
                "parameters": parameters
            }
        }

    def start_chat(self, history: List = None):
        """
        Starts a chat session. Returns self as the chat object.
        """
        # Convert Gemini history format to Ollama format if needed
        # Gemini: user, model
        # Ollama: user, assistant
        self.history = []
        if history:
            for h in history:
                role = "user" if h['role'] == 'user' else "assistant"
                self.history.append({"role": role, "content": h['parts'][0].text})
        return self

    def send_message(self, message: Any) -> 'LocalResponse':
        """
        Sends a message to the local model and returns a response object.
        """
        # 1. Handle Input
        if isinstance(message, str):
            self.history.append({"role": "user", "content": message})
        elif hasattr(message, 'parts'):
            # This is likely a function response from the Agent loop
            # We need to find the function_response part
            for part in message.parts:
                if part.function_response:
                    # Creating a tool message for Ollama
                    # The content of a tool message in Ollama is the result
                    # But Ollama expects a specific sequence: use call -> tool output
                    # The 'Assistant' role previously made the call.
                    # Now 'Tool' role (or User?) provides the output.
                    # Ollama terminology: role='tool'
                    
                    tool_response = part.function_response
                    self.history.append({
                        "role": "user",
                        "content": f"Observation: {json.dumps(tool_response.response)}" 
                    })
        elif isinstance(message, dict) and 'role' in message:
             self.history.append(message)


        # 2. Prepare Request
        messages_payload = []
        if self.system_instruction:
            messages_payload.append({"role": "system", "content": self.system_instruction})
        messages_payload.extend(self.history)
        
        print(f"DEBUG: Sending to Ollama model {self.model_name} (History len: {len(self.history)})...")

        # 3. Call Ollama
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=messages_payload,
                tools=self.ollama_tools
            )
            
            message_obj = response.get('message', {})
            content_text = message_obj.get('content', "")
            tool_calls = message_obj.get('tool_calls', [])
            
            # --- FALLBACK: If no native tool calls, check for JSON in content ---
            if not tool_calls and content_text:
                try:
                    # Look for JSON block
                    start = content_text.find('{')
                    end = content_text.rfind('}') + 1
                    if start != -1 and end != -1:
                        potential_json = content_text[start:end]
                        data = json.loads(potential_json)
                        
                        # Validate if it looks like a tool call structure we requested or just a simple call
                        # Agent logic usually expects: {"name": "func_name", "arguments": {...}}
                        if isinstance(data, dict) and "name" in data and "arguments" in data:
                             # It's a match! Construct a fake tool call object
                             print(f"DEBUG: Detected tool call in text: {data['name']}")
                             tool_calls = [{
                                 "function": {
                                     "name": data["name"],
                                     "arguments": data["arguments"]
                                 }
                             }]
                             # Optionally clear content text if it was just the tool call
                             # content_text = "" 
                except json.JSONDecodeError:
                    pass
            # -------------------------------------------------------------------
            
            # Update history with the assistant's response
            if tool_calls and not message_obj.get('tool_calls'):
                # parsing fallback update history with what we "heard" as a tool call?
                # Actually, simply appending the original content is safer for history consistency.
                self.history.append({"role": "assistant", "content": content_text})
            else:
                 self.history.append(message_obj)
            
            return LocalResponse(content_text, tool_calls)

        except Exception as e:
            print(f"ERROR calling Ollama: {e}")
            return LocalResponse(f"Error calling local model: {e}")

class LocalResponse:
    """
    Mimics the response object from Gemini
    """
    def __init__(self, text: str, tool_calls: List = None):
        self.text = text
        self.parts = [LocalPart(text, tool_calls)]

class LocalPart:
    def __init__(self, text, tool_calls=None):
        self.text = text
        self.function_call = None
        
        if tool_calls:
            # Taking the first tool call to mimic single function call structure of simple agents
            # Or handle multiple? The Agent loop expects `part.function_call` property on the first part.
            tc = tool_calls[0]
            self.function_call = LocalFunctionCall(tc['function']['name'], tc['function']['arguments'])

class LocalFunctionCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args
