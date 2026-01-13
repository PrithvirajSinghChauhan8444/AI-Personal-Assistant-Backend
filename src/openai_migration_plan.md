# OpenAI Migration Plan

This document outlines the steps to replace the Google Gemini integration with an OpenAI-compatible client (targeting `qwen/qwen3-32b`).

## 1. Dependencies and Configuration

- **Library**: We will need the `openai` Python library.
  - Action: `pip install openai`
- **Environment Variables**:
  - `OPENAI_API_KEY`: Required for authentication.
  - `OPENAI_BASE_URL`: (Optional but likely needed for "qwen/qwen3-32b") To point to the specific provider (e.g., OpenRouter, DeepSeek, or a local vLLM).
  - `MODEL_NAME`: Will be set to `qwen/qwen3-32b`.

## 2. Refactoring `base_agent.py`

The core logic currently relies on `google.generativeai` which handles history and tool schema generation automatically. The `openai` client is stateless and requires explicit JSON schemas for tools.

### Key Changes:

1.  **Imports**: Replace `google.generativeai` with `from openai import OpenAI`.
2.  **Initialization (`__init__`)**:
    - Instantiate `self.client = OpenAI(api_key=..., base_url=...)`.
    - The `self.history` list will now store standard OpenAI messages: `{"role": "user", "content": ...}`.
3.  **Tool Schema Conversion**:
    - **New Challenge**: Gemini accepts raw Python functions; OpenAI requires JSON Schemas.
    - **Solution**: Implement a helper method (properly formatting Python functions to JSON schemas) to convert `self.config.tools`.
4.  **Message Processing (`process_message`)**:
    - Replace `chat.send_message()` with `client.chat.completions.create()`.
    - Manually append user messages and assistant responses to `self.history`.
5.  **Response Handling (`_handle_response`)**:
    - Parse `response.choices[0].message.tool_calls` instead of `part.function_call`.
    - Execute the tool and append the result as a message with `role: "tool"` (and `tool_call_id`).

## 3. Refactoring `orchestrator.py`

- Replace the `genai.GenerativeModel` planner with the generic `OpenAI` client usage.
- Ensure the planning prompt uses the same stateless request pattern adapted for the OpenAI client.

## 4. Refactoring `standard_agents.py`

- Update `AgentConfig` for all agents to use `model_name="qwen/qwen3-32b"` (or read from global config).

## 5. Verification

- Run a test script to verify that:
  1.  The model receives the system instructions and history.
  2.  Tools are correctly defined and recognized by the model.
  3.  Tool execution loops work (Model calls tool -> Code executes -> Result sent back -> Model responds).
