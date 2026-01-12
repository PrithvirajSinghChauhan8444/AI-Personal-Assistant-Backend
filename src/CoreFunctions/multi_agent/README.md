# Multi-Agent System

This folder contains the core logic for the Multi-Agent System architecture.

## Importance

This module enables the AI Assistant to handle complex, multi-step tasks by breaking them down and assigning them to specialized agents. It supports recursive operations where the output of one agent can be used as the input for another.

## Contents

- **`__init__.py`**: Exposes the main classes for easy import.
- **`base_agent.py`**: Defines the `Agent` class, which wraps the Google Gemini model and handles tool execution (including recursive calls).
- **`orchestrator.py`**: Defines the `AgentManager` (Orchestrator), responsible for planning workflows and routing tasks to the appropriate agents.
- **`standard_agents.py`**: Contains pre-defined configurations for specialized agents like the Gmail Agent, WhatsApp Agent, and System Engineer.
