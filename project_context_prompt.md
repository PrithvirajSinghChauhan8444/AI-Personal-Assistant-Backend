# Project Context & Architecture Guide for AI Agents

This document describes the architecture, workflow, and coding patterns of the "Offline/Local AI Personal Assistant" project. Use this as a prompt or context when asking another AI to work on this or a similar codebase.

---

## 1. High-Level Architecture

The project is a modular, local-first AI agent designed to run offline (or hybrid) using local LLMs (e.g., via Ollama or similar) or efficient cloud models (like Gemma 2/3). It follows a **ReAct (Reason + Act)** loop pattern.

### **Core Flow**

1.  **Entry (`main.py`)**: The user inputs text.
    - Simple intent detection directs traffic (e.g., "summarize" -> `summarizer.py`, "check mail" -> `handle_gmail_command`).
    - Complex/General queries are sent to the **Agent Logic**.
2.  **Agent Logic (`src/CoreFunctions/agent_logic.py`)**:
    - **Phase 1 (Discovery)**: An LLM analyzes the user request to determine _intent_ and _necessary tools_.
    - **Phase 2 (ReAct Loop)**: A loop (max 10 steps) dealing with the LLM.
      - **Action**: LLM decides to call a tool (outputs JSON).
      - **Execution**: System executes the python function mapped to that tool.
      - **Observation**: System feeds the return value back to the LLM.
      - **Repeat**: Until the task is done.
3.  **Tool Registry (`src/CoreFunctions/tools.py`)**:
    - Central hub where all capabilities are registered.
    - Maps string names (e.g., `"send_mail"`) to actual Python functions.

---

## 2. Key File Roles

### `src/main.py` (The Gateway)

- **Role**: Main entry point. Handles the REPL (Read-Eval-Print Loop).
- **Logic**: Uses keyword matching for speed/efficiency on common tasks before loading the heavy LLM agent.

### `src/CoreFunctions/agent_logic.py` (The Brain)

- **Role**: Manages the LLM interaction loop.
- **Key Function**: `process_command(user_input)`
  - Initializes the session.
  - Iterates through the ReAct loop.
  - Parses JSON outputs from the LLM.
  - Calls functions from `AVAILABLE_TOOLS`.
  - Logs everything to `jarvis_execution_logs.json`.

### `src/CoreFunctions/tools.py` (The Hands)

- **Role**: Defines _what_ the agent can do.
- **Pattern**:
  1.  **Import**: Import heavy logic from `src/Apps/`.
  2.  **Wrap**: Create a simple wrapper function with a clear docstring (essential for the LLM to understand how to use it).
  3.  **Register**: Add the wrapper to the `AVAILABLE_TOOLS` dictionary.

### `src/Apps/` (The Skills)

- **Role**: Modular folders for specific features (Calendar, Gmail, System, etc.).
- **Structure**: Each app (e.g., `src/Apps/Calendar/`) contains its own logic scripts (e.g., `create_event.py`, `read_event.py`).

---

## 3. Workflow for Adding New Features

If you want the AI to add a new skill (e.g., "Spotify Control"), follow this strict workflow:

1.  **Create the App**:
    - Create `src/Apps/Spotify/`.
    - Write the core logic scripts (e.g., `play_music.py`, `search_song.py`).
2.  **Define the Tool**:
    - Open `src/CoreFunctions/tools.py`.
    - Import your new functions.
    - Write a wrapper function with a clear docstring:
      ```python
      def play_spotify_music(song_name):
          """Plays a song on Spotify. Input: song name string."""
          return spotify_handler.play(song_name)
      ```
3.  **Register the Tool**:
    - Add it to the `AVAILABLE_TOOLS` dictionary at the bottom of `tools.py`:
      ```python
      AVAILABLE_TOOLS = {
          ...,
          "play_music": play_spotify_music
      }
      ```
4.  **No Logic Changes Needed**:
    - Because `agent_logic.py` dynamically reads `AVAILABLE_TOOLS`, the agent _automatically_ knows how to use the new tool on the next run.

---

## 4. Prompt for the AI Agent

**Copy and paste this section to your coding assistant:**

> **System Context for AI Agent Development**
>
> You are working on a modular, local-first Python AI assistant project.
>
> **Architecture Overview:**
>
> - **`src/main.py`**: Entry point. Routes specific intents to handlers, generic ones to the Agent.
> - **`src/CoreFunctions/agent_logic.py`**: Implements a ReAct loop. It sends available tools to the LLM, parses JSON tool calls, executes them, and feeds the output back.
> - **`src/CoreFunctions/tools.py`**: The interface layer. It imports functional logic from `Apps/` and registers them in an `AVAILABLE_TOOLS` dictionary.
> - **`src/Apps/`**: Contains the actual business logic (Gmail api, Calendar api, System stats, etc.) organized by feature.
>
> **Your Task Workflow:**
>
> 1. **To add a new capability**:
>    - Create the functionality in a new folder under `src/Apps/`.
>    - Go to `src/CoreFunctions/tools.py`.
>    - Import the function.
>    - Wrap it in a function with a descriptive docstring (this docstring is the prompt for the internal LLM).
>    - Add it to the `AVAILABLE_TOOLS` map.
>
> **Code Style:**
>
> - Keep `main.py` lightweight.
> - `agent_logic.py` should remain generic; do not hardcode specific tools there.
> - Always rely on `AVAILABLE_TOOLS` in `tools.py` as the source of truth for agent capabilities.
