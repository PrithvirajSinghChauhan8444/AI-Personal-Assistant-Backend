# LangGraph Implementation Plan

This document outlines the plan for migrating the current custom ReAct loop to a structured Multi-Agent system using LangGraph.

## Goal

To implement a robust, stateful Multi-Agent system where a "Manager" agent supervises and delegates tasks to specialized "Worker" agents, using LangGraph for orchestration.

## Architecture: Supervisor-Worker Pattern

The system will consist of a **Supervisor Node (Manager)** and multiple **Worker Nodes**.

1.  **Manager (Supervisor)**:

    - Receives user input.
    - Plan tasks.
    - Decides which Worker agent to call next (Routing).
    - Synthesizes the final response.

2.  **Workers**:
    - Specialized agents wrapping specific tool sets (e.g., `GmailAgent`, `CalendarAgent`).
    - Execute tools and return observations to the state.

## File Breakdown & Responsibilities

### 1. `main_graph.py`

- **Purpose**: The entry point that constructs the StateGraph.
- **Content**:
  - Import agents and configs.
  - Define the `AgentState` (e.g., list of messages, `next` sender).
  - Add nodes (`Supervisor`, `Worker_1`, `Worker_2`, ...).
  - Define edges (Router logic from Supervisor -> Workers).
  - Compile the graph.
  - Expose a `process_request(user_input)` function.

### 2. `available_tools.py`

- **Purpose**: Tool Registry.
- **Content**:
  - Import existing functions from `src/CoreFunctions/tools.py`.
  - Wrap them as generic `LangChain` tools (using `@tool` decorator or `StructuredTool`).
  - Group them into lists (e.g., `gmail_tools`, `calendar_tools`).

### 3. `worker_define.py`

- **Purpose**: Factory for creating Worker Agents.
- **Content**:
  - Function to create an agent node.
  - Should take a model and a list of tools as input.
  - Returns a runnable that invokes the model and handles tool calling.

### 4. `worker_declare.py`

- **Purpose**: Configuration for specific Workers.
- **Content**:
  - Definitions of specific workers.
  - Example: "GmailWorker" uses `gmail_tools` and a specific system prompt.
  - Example: "CalendarWorker" uses `calendar_tools`.

### 5. `manager_define.py`

- **Purpose**: Class/Function to build the Manager Agent.
- **Content**:
  - Logic for the generic Supervisor node.
  - Usage of a model (e.g., Gemini-1.5-Pro) to act as the router.
  - Output parser to determine the `next` node.

### 6. `manager_declare.py`

- **Purpose**: Configuration for the Manager.
- **Content**:
  - The system prompt for the Manager (Supervisor).
  - List of managed workers to include in the router prompt options.

## Implementation Steps

1.  **Tools**: Populate `available_tools.py` by converting existing tools.
2.  **Workers**: Define worker configs in `worker_define.py` and implement the builder in `worker_declare.py`.
3.  **Manager**: Implement the supervisor logic in `manager_define.py`.
4.  **Graph**: Wire it all together in `main_graph.py`.
5.  **Test**: Switch `src/main.py` (or a test script) to use the new `main_graph.py` workflow.
