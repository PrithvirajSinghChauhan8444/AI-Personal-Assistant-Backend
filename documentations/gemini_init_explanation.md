# Gemini Model Initialization Breakdown

This document explains how the Google Gemini model is initialized and used within the `AI-Personal-Assistant` backend, specifically focusing on `base_agent.py`.

## 1. Library Import and Configuration

In `src/CoreFunctions/multi_agent/base_agent.py`, the initialization begins with importing the `google.generativeai` library (aliased as `genai`).

```python
import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
```

- **Environmental Variables**: The system loads environment variables using `dotenv`.
- **API Key Retrieval**: It fetches `GEMINI_API_KEY` from the environment.
- **Configuration**: `genai.configure(api_key=api_key)` sets the global API key for the library. This allows subsequent model calls to be authenticated.

## 2. Agent Initialization

The `Agent` class encapsulates the model usage. When an agent is instantiated:

```python
class Agent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.history = []
        self._model = self._setup_model()  # <--- Creation happens here
        self._chat = self._model.start_chat(history=[]) # <--- Chat session starts here
```

- **`_setup_model()`**: This internal method constructs the specific `GenerativeModel` instance.
- **`start_chat()`**: Immediately after model creation, a chat session is started. This session maintains conversation history (context) automatically.

## 3. Model Creation Logic (`_setup_model`)

The `_setup_model` method is where the `GenerativeModel` object is actually built with specific parameters:

```python
    def _setup_model(self):
        # 1. Tool Mapping
        selected_tools = []
        self.functions = {}

        for tool_name in self.config.tools:
            # logic to look up tool functions from AVAILABLE_TOOLS map
            # ...
            selected_tools.append(func)

        # 2. Model Instantiation
        return genai.GenerativeModel(
            model_name=self.config.model_name,      # e.g., "gemini-1.5-flash"
            tools=selected_tools if selected_tools else None, # Function calling tools
            system_instruction=self.config.system_instruction, # System Prompt
            generation_config=genai.types.GenerationConfig(
                temperature=self.config.temperature # Creativity setting
            )
        )
```

- **`model_name`**: The specific version of Gemini to use (e.g., `'gemini-1.5-flash'`).
- **`tools`**: A list of Python functions (tools) that the model is allowed to call. The library handles converting these into a schema the model understands.
- **`system_instruction`**: The prompt that defines the agent's persona and rules.
- **`generation_config`**: Parameters like `temperature` that control the randomness of the output.

## 4. Summary

To initialize a Gemini model in this system:

1.  **Configure `genai`** with the API key globally.
2.  **Instantiate `GenerativeModel`** via `_setup_model` with the desired model name, tools, and system instructions.
3.  **Start a Chat Session** using `start_chat()` to enable interactive, multi-turn conversation capabilities.
