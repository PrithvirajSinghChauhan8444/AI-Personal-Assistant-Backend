# AI Personal Assistant - Project Documentation

This document contains complete technical and operational details of the AI Personal Assistant Backend project. It is designed to allow a developer to replicate or understand the system fully.

## 1. Project Overview

**Purpose**: A local, offline-capable (mostly) and secure AI personal assistant that can interact with the user's system, manage communications (WhatsApp, Email), and organize tasks.

**Core Philosophy**: "LLMs decide, Code executes." The AI plans actions, but Python functions perform the actual operations.

## 2. Technology Stack

- **Language**: Python 3.10+
- **AI Models**: Google Gemini (via `google-generativeai`).
  - `gemma-3-12b-it`: For routing and fast tasks.
  - `gemma-3-27b-it`: For complex reasoning and coding.
- **WhatsApp Integration**: [WAHA (WhatsApp HTTP API)](https://waha.devlike.pro/) running in Docker.
- **Database**:
  - JSON files for lightweight storage (`Memory/user_info.json`, `src/Apps/WhatsApp/contacts.json`).
  - ChromaDB (implied in `vector_memory.py`) for semantic search.
- **Environment**: `.env` for secrets management.

## 3. Architecture & Directory Structure

```text
AI-Personal-Assistant-Backend/
├── .env                # API Keys (Gemini) and Secrets
├── docker-compose.yml  # WAHA Service configuration
├── Dockerfile          # For containerizing the backend (optional)
├── requirements.txt    # Python dependencies
├── src/
│   ├── Apps/           # Functional Modules
│   │   ├── Calendar/   # Google Calendar integration
│   │   ├── Gmail/      # Gmail API integration
│   │   ├── WhatsApp/   # WAHA integration
│   │   ├── System/     # System stats (CPU/RAM)
│   │   └── FileOperations/ # Read/Write/List files
│   ├── CoreFunctions/  # The Brain
│   │   ├── multi_agent.py  # NEW: Multi-Agent Orchestrator
│   │   ├── tools.py        # Central Registry of all available tools
│   │   ├── agent_logic.py  # (Legacy) Single-agent ReAct loop
│   │   ├── memory.py       # JSON-based persistent memory
│   │   └── auth_utils.py   # Password verification logic
│   └── main.py         # Entry point (Legacy)
└── Memory/             # User data storage
```

## 4. Key Components

### A. Multi-Agent Orchestrator (`src/CoreFunctions/multi_agent.py`)

The system uses an **Orchestrator** pattern:

1.  **AgentManager**: Receives user input (e.g., "Check RAM and WhatsApp me").
2.  **Planner**: Breaks the request into steps:
    - Step 1: Get RAM (assigned to `SystemEngineer`).
    - Step 2: Send WhatsApp (assigned to `Communicator`).
3.  **Agents**:
    - `GeneralAssistant`: Chit-chat.
    - `SystemEngineer`: File & System Ops.
    - `Communicator`: Messages & Calendar.

### B. Tools Registry (`src/CoreFunctions/tools.py`)

A massive dictionary `AVAILABLE_TOOLS` mapping string keys (e.g., "send_whatsapp") to actual Python functions. This is the interface the LLM uses.

### C. WhatsApp Service

Uses **WAHA** (WhatsApp HTTP API) running on port `3000`.

- **Status**: Managed via `docker-compose.yml`.
- **Interaction**: `src/Apps/WhatsApp/sending_message.py` sends HTTP POST requests to the local WAHA container.

## 5. Setup & Installation Guide

### Prerequisites

1.  **Python 3.10+** installed.
2.  **Docker Desktop** installed (for WhatsApp).
3.  **Google Gemini API Key**.

### Step 1: Clone & Environment

```bash
git clone <repo-url>
cd AI-Personal-Assistant-Backend
python -m venv .venv
# Activate: .venv\Scripts\activate (Windows) or source .venv/bin/activate (Linux)
pip install -r requirements.txt
```

### Step 2: Configuration (.env)

Create a `.env` file in the root:

```ini
GEMINI_API_KEY=your_gemini_api_key_here
SYSTEM_PASSWORD=your_secure_password  # For dangerous actions like deleting files
```

### Step 3: Start WhatsApp Service

```bash
docker-compose up -d
```

- Visit `http://localhost:3000/dashboard` to scan the QR code.

### Step 4: Run the Assistant

**Option A: Multi-Agent Mode (Recommended)**

```bash
python src/CoreFunctions/multi_agent.py
```

**Option B: Legacy Single-Agent**

```bash
python src/CoreFunctions/vvv.py
```

## 6. Development Guidelines for Clones

- **Adding Tools**:
  1.  Create the function in `src/Apps/<Module>/`.
  2.  Import it in `src/CoreFunctions/tools.py`.
  3.  Add it to `AVAILABLE_TOOLS`.
  4.  Update `multi_agent.py` to allow specific agents to use it.
- **Security**: Critical functions (`write_file`, `launch_app`) are wrapped with `verify_password()` in `tools.py`. Ensure this pattern is maintained.

## 7. Troubleshooting

- **Import Errors**: Always run python from the root directory: `python src/CoreFunctions/...`. The scripts include `sys.path.append` fixes but root execution is safest.
- **WhatsApp Fails**: Ensure Docker is running (`docker ps`) and the phone is connected via `http://localhost:3000`.
- **Gemini Error**: Check `GEMINI_API_KEY` validity.
