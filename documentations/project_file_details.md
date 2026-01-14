# Project File Details

This document provides a detailed overview of the files in this project, explaining their purpose, functionality, and necessity.

---

## 📂 Root Directory

- **`Dockerfile`**

  - **Purpose:** Defines the Docker image for the application.
  - **When needed:** During container build (`docker build`).
  - **Why:** Ensures a consistent runtime environment across different machines.

- **`docker-compose.yml`**

  - **Purpose:** Orchestrates the multi-container setup (Backend + Services like WAHA).
  - **When needed:** When starting the full stack (`docker-compose up`).
  - **Why:** Manages networking, volumes, and dependencies between containers.

- **`requirements.txt`**

  - **Purpose:** Lists Python dependencies.
  - **When needed:** For installation (`pip install -r requirements.txt`).
  - **Why:** Ensures all necessary libraries are present.

- **`README.md`**
  - **Purpose:** High-level project introduction and usage guide.
  - **When needed:** For on-boarding new developers.
  - **Why:** Standard documentation entry point.

---

## 📂 Configuration (`config/`)

- **`config/credentials.json`**

  - **Purpose:** Google Cloud OAuth2 Client Secrets.
  - **When needed:** During the initial authentication flow.
  - **Why:** Required to identify the application to Google APIs.

- **`config/token.json`**

  - **Purpose:** Stores the user's access and refresh tokens.
  - **When needed:** At runtime to authenticate API requests without re-login.
  - **Why:** Persists user session securey.

- **`config/.env`** (System File)
  - **Purpose:** Stores environment variables (API Keys, Passwords).
  - **When needed:** At application startup.
  - **Why:** Secures sensitive data like `GEMINI_API_KEY`.

---

## 📂 Source Code (`src/`)

### 🔹 Entry Points & Main Logic

- **`src/main.py`**

  - **Purpose:** The primary entry point for the Multi-Agent system.
  - **When needed:** Used to run the application (`python src/main.py`).
  - **Why:** Initializes the Agency, loads environment variables, and starts the main interactive loop.

- **`src/api_server.py`**
  - **Purpose:** HTTP API Server (likely FastAPI/Flask) for the backend.
  - **When needed:** When interacting with the assistant via a frontend or external webhook.
  - **Why:** Exposes internal logic as accessible web endpoints.

### 🔹 Core Functions (`src/CoreFunctions/`)

- **`src/CoreFunctions/agent_logic.py`**

  - **Purpose:** Implements a single-agent ReAct (Reasoning + Acting) loop using Gemini.
  - **Details:** Contains `process_command` (the loop), `discover_tools_and_data` (intent analysis), and structured JSON logging.
  - **When needed:** When running the agent in a single-threaded logic mode.
  - **Why:** Provides the core cognitive architecture for the agent to use tools.

- **`src/CoreFunctions/auth_utils.py`**

  - **Purpose:** Manages Google Authentication and Action Verification.
  - **Details:** Handles OAuth flows (`get_valid_credentials`), token refreshing, and sensitive action password barriers (`verify_password`).
  - **When needed:** Whenever the agent accesses Google APIs or performs sensitive tasks.
  - **Why:** Ensures security and proper authorization.

- **`src/CoreFunctions/vvv.py`** (Secure Agent Implementation)

  - **Purpose:** A standalone, secure version of the agent with a Planner/Executor split.
  - **Details:** Implements `plan_tasks` (Planner Model) and `process_command` (Executes code). Includes strict validation logic.
  - **When needed:** For verifying safer, planned execution flows.
  - **Why:** Provides a more robust, supervised execution model compared to the raw loop.

- **`src/CoreFunctions/tools.py`**

  - **Purpose:** A registry of all available tools.
  - **Details:** Maps function names (string) to actual Python callables.
  - **When needed:** By the LLM to know what it can do, and by the execution loop to call functions.
  - **Why:** The bridge between language model decisions and code execution.

- **`src/CoreFunctions/path_utils.py`**

  - **Purpose:** Utilities for resolving file paths relative to the project root.
  - **Why:** Ensures code runs correctly regardless of the current working directory.

- **`src/CoreFunctions/memory.py` & `src/CoreFunctions/vector_memory.py`**

  - **Purpose:** Handles long-term memory retrieval and storage.
  - **When needed:** When the user asks purely informational questions or "recall" requests.
  - **Why:** Gives the agent state persistence beyond the immediate context window.

- **`src/CoreFunctions/command_handler.py`**
  - **Purpose:** Likely handles parsing or routing specific command patterns.

### 🔹 Application Modules (`src/Apps/`)

_Each module here contains specific logic for different features._

- **`src/Apps/briefing/`**: Logic for daily briefings (news, calendar summaries).
- **`src/Apps/Calendar/`**:
  - **`calendar_service.py`**: Interacts with Google Calendar API.
  - **`create_event.py`**: Logic for adding events.
  - **`read_events.py`**: Logic for fetching upcoming events.
- **`src/Apps/Gmail/`**:
  - **`gmail_handler.py`**: Interacts with Gmail API.
  - **`gmail_sender.py`**: Sending logic.
  - **`read_unread.py`**: Reading logic.
- **`src/Apps/Spotify/`**:
  - **`spotify_client.py`**: Controls Spotipy client for music playback.
- **`src/Apps/SystemControl/`**:
  - **`execution.py`**: **Critical file.** Handles `run_terminal_command`, `run_python_script`, and `launch_app`. Managing path resolution and app launching via `AppOpener` or `subprocess`.
  - **`allowed_apps.json`**: Whitelist/Mapping of app names to executables.
- **`src/Apps/WhatsApp/`**: Logic for sending and receiving WhatsApp messages (via WAHA).

---

## 📂 Documentation (in `documentations/`)

- **`project_file_details.md`**: (This file)
- **`PROJECT_DOCUMENTATION.md`**: Broad overview.
- **`gemini_init_explanation.md`**: Technical details on Gemini setup.
- **`openai_migration_plan.md`**: Legacy/Future planning doc.
- **`project_context_prompt.md`**: System instructions for the LLM.
- **`unimportant_files.md`**: List of deletable/low-priority files.
