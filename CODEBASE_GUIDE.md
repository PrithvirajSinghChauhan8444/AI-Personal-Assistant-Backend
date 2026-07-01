# 📖 AI Personal Assistant Backend - Codebase & File Guide

This document provides a structural layout and functional mapping of every Python source file in the AI Personal Assistant Backend repository. It details each file's role in the complete system, the classes and functions it provides, and their specific interfaces.

---

## 🗺️ How to Understand the Working of the Assistant

To quickly understand how the AI Personal Assistant behaves, processes requests, and interacts with the system, follow this recommended walkthrough:

### 1. Start with the Entry Point

* **File**: [main_graph.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/main_graph.py)
* **What to look for**:
  * [process_request_interactive()](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/main_graph.py#L441): The main terminal loop that starts the assistant. Note how it loads previous session context, prompts the user to resume interrupted tasks (if any), and sets up the active execution session.
  * [create_graph()](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/main_graph.py#L33): Compiles the cyclic state machine using LangGraph. This defines the overall node connectivity and the execution flow of the assistant.

### 2. Trace the Request Lifecycle (State Graph Nodes)

Requests progress through isolated, specialized nodes that coordinate via the shared `AgentState` dictionary defined in [state.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/state.py):

1. **Context Ingestion**: [memory_nodes.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/memory_nodes.py) loads the user profile, searches vector databases, and checks for simple greets (fast path) via `MemoryInjector`.
2. **Metadata Collection**: [system_state.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/system_state.py) aggregates active workers list, chat history metrics, and LLM thinking parameters to save to `system_state`.
3. **Decomposition**: [task_router.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/task_router.py) uses a high-cognition model to break the user goal into structured subtasks (a Directed Acyclic Graph plan).
4. **Execution Scheduling**: [orchestrator.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/orchestrator.py) monitors task dependencies, forks parallel ready subtasks, resets orphaned tasks, and dynamically routes them to worker agents.
5. **Action Workers**: Discovered dynamically via [registry.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/registry.py) and compiled via [executor.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/executor.py). Each worker executes ReAct agents with strictly sandboxed tools.
6. **Output Synthesis**: [finalizer.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/finalizer.py) merges the subtasks' outcomes into a single unified response.
7. **Self-Learning**: [Reflection](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/memory_nodes.py) node runs in the background to extract user facts and save them for the next turn.

### 3. Read the Execution Logs (Observability)

The easiest way to see the assistant "in action" without debugger breakpoints is to run a query and inspect the generated session logs:

* **Human-Readable Traces**: Read `Memory/logs/latest.log`. It lists precise start/end boundaries of state graph nodes, worker thoughts, tool calls, parameters, and return values in a nested, clean console format.
* **Structured Traces**: Read `Memory/logs/latest.json` to inspect raw state updates, reducer operations, and node timings.
* **Code Reference**: See [logger.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/logger.py).

### 4. Understand Available Tools & Skills

* **Concrete Python Tools**: Check [tools.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/tools.py) to see the execution logic of system control, calendar, gmail, classroom, browser, and file utilities.
* **Procedural Skill Manuals**: Read the markdown manuals in `Skills/` (e.g. `Skills/SystemControl/` or `Skills/Gmail/`) to understand the step-by-step instructions the LLM reads to perform multi-stage workflows.

---

## 📂 Project Directory Structure

```text
ROOT/
├── config/                  # Configuration files (API keys, OAuth credentials, workers_config.json)
├── scripts/                 # Setup, verification, and experimental scrape utilities
│   ├── browser_experiment/  # Prototypes for DOM processing and HTML-to-Markdown conversions
│   ├── clear_skills.py
│   ├── do_setup_ytmusic.py
│   ├── migrate_skills.py
│   ├── setup_ytmusic.py
│   └── verify_ytmusic.py
├── src/                     # Core codebase
│   └── CoreFunctions/       # Foundation architecture, security wrappers, and LangGraph engine
│       ├── Integrations/    # Modular integrations with desktop apps and external APIs
│       │   ├── Automation/  # Scheduled background tasks
│       │   ├── Briefing/    # Weather and news aggregators
│       │   ├── Calendar/    # Google Calendar services
│       │   ├── Classroom/   # Google Classroom and Drive material management
│       │   ├── FileOperations/ # Sandboxed filesystem utility functions
│       │   ├── Github/      # Local Git repository and GitHub API operations
│       │   ├── Gmail/       # Full Google Mail attachments and threads handling
│       │   ├── Google/      # Google Tasks services
│       │   ├── Spotify/     # Spotify auth client and media controls
│       │   ├── System/      # Clipboard, downloader, and OS system monitors
│       │   └── SystemControl/ # Command line execution and app launcher
│       │
│       ├── StateGraph/      # LangGraph state machine flow definitions
│       │   ├── Workers/     # Directories defining individual worker classes and prompts
│       │   │   ├── BrowserWorker/ # Web search and automation worker
│       │   │   ├── ClassroomWorker/ # Classroom tasks worker
│       │   │   ├── GithubWorker/ # Git repository worker
│       │   │   ├── GmailWorker/ # Email operations worker
│       │   │   ├── MemoryWorker/ # Facts retrieval worker
│       │   │   ├── MiscWorker/  # YTMusic and custom automation scripts
│       │   │   ├── ObsidianWorker/ # Multi-agent Obsidian Manager team
│       │   │   ├── ProductivityWorker/ # Tasks and scheduling worker
│       │   │   └── SystemWorker/ # System diagnostic and execution worker
│       │   │
│       │   ├── registry.py  # Decorators for plugin worker discovery
│       │   ├── executor.py  # ReAct compilation, transactions, and large outputs cache
│       │   ├── system_state.py # Environment configuration and history metadata node
│       │   ├── task_router.py # Pydantic LLM planning node (DAG planner)
│       │   ├── orchestrator.py # Fork-join task scheduler and self-healing checker
│       │   ├── finalizer.py   # Final output synthesizer node
│       │   └── main_graph.py  # Compile and run loop for LangGraph cyclic state machine
│       │
│       ├── auth_utils.py    # Google OAuth2 credentials encryption and stack introspection
│       ├── file_vector_store.py # Local document chunking and FAISS indexing search
│       ├── logger.py        # Concurrent text & JSON session logging
│       ├── memory.py        # SQLite persistent key-value cognitive databases
│       ├── path_utils.py    # Directory boundary resolution helpers
│       ├── security_utils.py # Shell sanitization and path directory sandbox checks
│       ├── tools.py         # Concrete tool execution logic definitions
│       ├── unified_memory.py # Cache database engines (SQLite/Redis/Postgres wrapper)
│       └── vector_memory.py  # Chromadb semantic vector memory
└── tests/                   # Automated validation suites for testing registry, configurations, database cache, etc.
```

---

## 🏗️ 1. Core Functions System (`src/CoreFunctions/`)

These files form the foundation of the assistant's infrastructure, providing memory management, security boundaries, authentication, RAG indices, and utility helpers.

---

### 🗃️ [unified_memory.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/unified_memory.py)

* **Role in the Assistant**: Implements a cache layer (SQLite/Redis/Postgres) that enables thread-safe state synchronization and transactional updates across concurrent worker threads. It also parses XML formatting tags from outputs.

#### Classes

##### `BaseMemoryEngine`

Abstract Base Class defining the standard interface for memory cache backends.

* `set(key, value, ttl_seconds)`: Abstract method to cache a key.
* `get(key)`: Abstract method to retrieve a cached key.
* `delete(key)`: Abstract method to remove a key.
* `keys(pattern)`: Abstract method to retrieve keys matching a regex/glob pattern.
* `acquire_lock(lock_name, lease_time)`: Abstract lock acquisition.
* `release_lock(lock_name)`: Abstract lock release.

##### `SQLiteMemoryEngine`

SQLite implementation of the memory engine, supporting thread-safe operation and lazy TTL cleanup.

* `__init__(db_path)`: Binds to the local SQLite database path.
* `_get_connection()`: Establishes a thread-local SQLite connection.
* `_init_db()`: Initializes the schema table (`cache`) for keys, values, and expiration times.
* `set(key, value, ttl_seconds)`, `get(key)`, `delete(key)`, `keys(pattern)`, `acquire_lock(lock_name, lease_time)`, `release_lock(lock_name)`: Implements thread-safe cache operations.

##### `RedisMemoryEngine`

Redis database engine utilizing native Redis commands and distributed locks.

* `__init__(redis_client)`: Wraps an active Redis client.
* `_full_key(key)`: Prefixes keys with system identifiers.
* `set(key, value, ttl_seconds)`, `get(key)`, `delete(key)`, `keys(pattern)`, `acquire_lock(lock_name, lease_time)`, `release_lock(lock_name)`: Implements operations on Redis server.

##### `UnifiedMemory`

The central manager singleton exposing the thread-safe API to the rest of the application.

* `__new__(cls)`: Returns singleton instance.
* `__init__(db_path)`: Instantiates the manager configuration.
* `_initialize_engine()`: Automatically falls back to SQLite if no local Redis server is running.
* `extract_entities(text)`: Parses custom tag formats from inputs and returns annotations.
* `init_transaction(txn_id)`: Registers a transient buffer for buffering changes during a transaction.
* `start_transaction()`: Starts a transaction context and returns transaction IDs and reset tokens.
* `commit_transaction(txn_id, token)`: Commits buffered changes to the database.
* `discard_transaction(txn_id, token)`: Clears transaction buffers.
* `store_memory(key, data, sharable, persistent, ttl_seconds)`: Routes data write (buffered if inside transaction).
* `retrieve_memory(key)`: Reads a key-value pair from transaction buffers or the active engine.
* `delete_memory(key)`: Deletes key from cache.
* `list_keys(pattern)`: Lists active keys matching a pattern.

---

### 🛡️ [security_utils.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/security_utils.py)

* **Role in the Assistant**: Acts as the gatekeeper validating that all shell operations, script executions, and file reads/writes remain strictly inside the user's sandboxed environment paths.

#### Functions

* `is_path_safe(target_path)`: Resolves symlinks, checks path prefixes, and returns a boolean indicating if the target resides inside whitelisted workspaces.
* `is_extension_safe(filepath)`: Verifies the file extension is not blacklisted (e.g. executable binaries).
* `is_command_safe(command, cwd)`: Evaluates shell command arguments and blocks dangerous subshells, redirects, or relative paths that traverse outside the sandbox.

---

### 🔑 [auth_utils.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/auth_utils.py)

* **Role in the Assistant**: Coordinates Google service credentials. It encrypts cached JSON credentials using Fernet cryptography and serializes console inputs (`verify_password`) when parallel workers request authentication.

#### Functions

* `get_config_dir()`: Resolves root configuration directories.
* `get_encryption_key()`: Retrieves or derives key for Fernet decryption (uses passwords or environment overrides).
* `load_encrypted_json(filepath)`: Decrypts and reads credentials from file paths.
* `save_encrypted_json(filepath, data)`: Encrypts and writes dictionaries to files with locked POSIX permissions.
* `get_valid_credentials(account)`: Master auth function that checks token validity, refreshes expired tokens, or spawns browser flows for initial OAuth logins.
* `get_stdin_prompt_banner(action_type, reason)`: Uses call stack inspection (`inspect.stack()`) to find the calling worker and task, formatting this context into a prominent warning card.
* `verify_password()`: Prompts for system passwords when critical command lines or settings updates are triggered.

---

### 🧭 [file_vector_store.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/file_vector_store.py)

* **Role in the Assistant**: Enables semantic document search. Scans directories, processes text files into chunks (tracking line boundaries), indexes them inside a local FAISS database, and performs RAG QA over single or grouped files.

#### Functions

* `_get_model()`: Lazily loads SentenceTransformer models on demand.
* `_load_index()`: Lazily loads FAISS indexes from files.
* `_load_data()`: Loads matched metadata maps for chunks.
* `_save(index, data)`: Commits indices to disk.
* `chunk_text_by_lines(text, max_chars, overlap_lines)`: Slices file content into overlapping chunks with precise source lines.
* `index_file(filepath)`: Computes embeddings for chunks in a file and registers them.
* `index_directory_recursive(dir_path)`: Automatically indexes all code and text files inside a workspace.
* `search_files_semantically(query, k)`: Performs semantic searches and returns matching passages.
* `rag_qa_file(query, filepath)`: Restricts context to a specific file and generates summaries or answers query using the LLM.

---

### 🗄️ [vector_memory.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/vector_memory.py)

* **Role in the Assistant**: Powers the long-term semantic memory and procedural skills cache. It embeds user facts and procedural guides (`SKILL.md` documents), indexing them into vector databases (`skills_index.faiss`) for quick lookup during queries.

#### Functions

* `_get_model()`, `_load_index()`, `_load_data()`, `_save(...)`: Lazy initialization handlers for indices.
* `store_vector(text)`: Embeds new facts or logs into long-term user history vector memory.
* `search_vector(query, k)`: Retrieves relevant historical facts from user context.
* `_load_skills_index()`, `_load_skills_data()`: Helper methods to load skill databases.
* `rebuild_skills_vector_store()`: Scans all skill manuals under `Skills/`, extracts metadata (descriptions, steps, tags), builds a FAISS index, and saves it.
* `search_skills_vector(query, k)`: Queries the procedural index to fetch execution manuals matching user requests.

---

### 🪵 [logger.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/logger.py)

* **Role in the Assistant**: Provides execution tracking. It records sequential console logs (indenting loops and nesting calls) and captures structured JSON trace arrays to support visual debugging tools.

#### Functions

* `set_thread_session_id(session_id)`: Maps session logs to specific request threads.
* `get_current_session_id()`: Fetches the thread's session ID.
* `init_session_logger(session_id, primary_goal)`: Initializes log streams.
* `log_message(message)`: Appends structured text traces.
* `log_node_start(node_name, input_state)` / `log_node_end(node_name, output_state)`: Captures graph nodes transition checkpoints.
* `log_worker_start(...)`, `log_worker_thought(...)`, `log_worker_tool_call(...)`, `log_worker_tool_response(...)`, `log_worker_end(...)`: Logs the granular steps of individual worker agents.
* `log_error(source, message, details)`: Logs exceptions.
* `end_session_logger(final_response, success)`: Writes footers and terminates log files.

---

### 🗃️ [memory.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/memory.py)

* **Role in the Assistant**: Manages flat configuration queries and interfaces with `UnifiedMemory` database lookup tables (`user`, `current`, `past`) to store preference details and prevent duplicates.

#### Functions

* `store_memory(category, key, value)`: Updates profile records in the unified SQL database cache.
* `fetch_memory(category, key)`: Look up key-value pairs (falls back sequentially through `user` -> `current` -> `past` tables).
* `delete_memory(category, key)`: Deletes cognitive key-value entries.

---

### 🛠️ [tools.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/tools.py)

* **Role in the Assistant**: The central registry defining the functional interface of all tools. It links external scripts and integration endpoints (`src/CoreFunctions/Integrations/`) to execution workers. These functions enforce password validation cards for sensitive tools and handle browser locks when human interventions are needed.

#### Selected Functions

* `remember(key, value, category)` / `recall(key)`: Memory database helpers.
* `fetch_unread_mails(limit, account)` / `send_gmail(...)` / `reply_to_gmail(...)`: Gmail client functions.
* `check_calendar_events(max_results, account)` / `add_calendar_event(...)`: Google Calendar tools.
* `fetch_classroom_courses(account)` / `download_classroom_materials_tool(...)`: Google Classroom tools.
* `get_system_health()`, `get_weather(location)`, `web_search(query)`: General information helpers.
* `run_code(code)`: Sandbox-wrapped terminal tool.
* `control_media_player(action)`, `lock_desktop_screen()`, `suspend_desktop_system()`: Local OS actions.
* `create_file_tool(path, content)` / `rag_file_qa_tool(query, filepath)`: Sandboxed file utilities.
* `run_terminal_tool(command)` / `run_python_tool(path)`: Secure command/script runners.
* `create_obsidian_note(...)` / `create_or_update_obsidian_canvas(...)`: Vault note manipulators.
* `browser_navigate(url)` / `browser_click(id)`: Interactive browser sub-agent control tools.
* `schedule_delayed_task_tool(...)` / `list_scheduled_tasks_tool()`: Background scheduler triggers.

---

### 🔀 [path_utils.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/path_utils.py)

* **Role in the Assistant**: Resolves absolute directory paths dynamically to prevent file reference breakages when executed from arbitrary working directories.

#### Functions

* `get_config_path(filename)`: Returns the absolute path of a config file inside the `config/` directory.

---

## 🕸️ 2. State Graph Engine (`src/CoreFunctions/StateGraph/`)

These files define the LangGraph cyclic state machine. They schedule tasks, coordinate workers, route requests, compile states, and manage final responses.

---

### 🔌 [registry.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/registry.py)

* **Role in the Assistant**: Handles dynamic registration and config synchronization. It scans the `Workers/` directory, registering ReAct agents via class decorators.

#### Classes & Decorators

* `BaseWorker`: Interface representing the required fields for workers (name, instruction prompts, tool registries, routing rules).
* `WorkerRegistry`: Registry manager keeping a mapped list of active workers.
  * `register(worker_cls)`: Class decorator to declare and initialize new workers.
  * `load_and_sync_config()`: Synchronizes active status and designated models with `config/workers_config.json`.
  * `get_worker(name)`: Returns registered instance by name.
* `scan_and_register_workers(workers_dir, force_reload)`: Dynamically walks subfolders on runtime to load classes.

---

### ⚡ [executor.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/executor.py)

* **Role in the Assistant**: The compiled worker executor. It instantiates LLM models (Gemini vs local Ollama) based on worker configs, loads semantic vector skills cache instructions, executes transaction blocks via `UnifiedMemory`, and intercepts human-in-the-loop triggers.

#### Functions

* `get_model_for_worker(worker_name)`: Maps configured worker strings to specific model instances (e.g. ChatGoogleGenerativeAI with thinking budgets or ChatOllama).
* `compile_worker_agents()`: Compiles ReAct executors from LangGraph.
* `_run_ephemeral_agent(...)` / `_run_async_ephemeral_agent(...)`: Isolated runners executing agents within SQL database transactions.
* `_update_state_completed(state, task_id, final_data)`: Marks subtasks as completed. Automatically offloads output data exceeding 2000 chars to local cache files, saving `__file_reference__` pointers to state to prevent LLM prompt bloat.

---

### 📊 [system_state.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/system_state.py)

* **Role in the Assistant**: State graph node that gathers execution metrics.

#### Functions

* `system_state_node(state)`: Records active workers info, chat history sizes, and token boundaries, returning a dictionary to populate `system_state`.

---

### 📈 [state.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/state.py)

* **Role in the Assistant**: Declares the `AgentState` schema, representing the globally shared memory model of the execution graph. It contains reducer merging operators to aggregate state mutations without race conditions.

#### Classes

##### `SubTask`

TypedDict representation of a task block (e.g. status, dependencies, assigned worker).

##### `AgentState`

The master state dictionary containing:

* `primary_goal`: Original user query.
* `active_subtasks`: Planning DAG list using `merge_subtasks`.
* `working_memory`: Dynamic values updated using `merge_dict`.
* `completed_tasks`: Summaries of executed actions using `merge_dict`.
* `error_logs`: Accumulated logs list using `merge_error_logs`.
* `final_response`: Synthesis text.
* `chat_history`: Conversation thread.
* `system_state`: Real-time metadata variables dictionary.

---

### 🗺️ [task_router.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/task_router.py)

* **Role in the Assistant**: Analyzes primary goals and builds an execution DAG (Directed Acyclic Graph) of subtasks, assigning workers and resolving processing dependencies.

#### Classes

* `SubTaskModel`: Pydantic validator representing individual planned tasks.
* `TaskPlan`: Pydantic object validating lists of planned tasks.

#### Functions

* `task_router_node(state)`: Directs the prompt to the planner LLM, fetches a structured DAG plan, and saves it into the state's `active_subtasks`.

---

### ⚙️ [orchestrator.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/orchestrator.py)

* **Role in the Assistant**: The control hub. It reads the subtask list to route execution. It forks parallel tasks to their respective workers, resets orphaned tasks, and handles blocked dependency deadlocks.

#### Functions

* `orchestrator_node(state)`: Scans subtasks, detects completed prerequisites, marks ready items as `in_progress`, and transitions them to the router.
* `orchestrator_router(state)`: Binds to LangGraph's conditional routing to select next nodes (e.g., executing worker nodes, returning to finalizers, or looping).

---

### 🧘 [memory_nodes.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/memory_nodes.py)

* **Role in the Assistant**: Handles pre-execution enrichment (`MemoryInjector`) and post-execution learning (`Reflection`). It loads profile parameters and queries semantic manuals, then extracts persistent facts when operations conclude.

#### Functions

* `is_personal_query(query)`: Quickly assesses whether personal memory context needs to be loaded.
* `check_fast_path(primary_goal)`: Bypasses the LangGraph state machine for simple commands (e.g. checking volume or current time) for instant execution.
* `memory_injector_node(state)`: Merges matching RAG memories and profile parameters into the active execution state.
* `reflection_node(state)`: Background fact extractor that updates vector profiles and rebuilds index stores.

---

### 🏁 [finalizer.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/finalizer.py)

* **Role in the Assistant**: Synthesizes the results from all completed subtasks into a coherent final response for the user.

#### Functions

* `output_finalizer_node(state)`: Synthesizes completed subtask data into the state's `final_response` text using the LLM.

---

### ⛓️ [main_graph.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/StateGraph/main_graph.py)

* **Role in the Assistant**: Compiles the nodes and routing channels into an executable LangGraph instance. It supports checkpointers to resume interrupted execution runs.

#### Classes

##### `CLIStatusVisualizer`

Manages terminal loaders and status updates during execution.

#### Functions

* `memory_injector_router(state)`: Determines route transitions after injecting memories (can redirect to output finalizer on fast path matches).
* `create_graph()`: Constructs the LangGraph instance.
* `save_interrupted_task_checkpoint(state_values, status)`: Serializes session state data to files.
* `clear_interrupted_task_checkpoint()`: Clears active checkpoints.
* `run_graph_execution(...)`: Runs graph execution streams and records state steps.
* `process_request_interactive()`: Starts the interactive terminal shell.

---

## 📲 3. Modular Integrations & APIs (`src/CoreFunctions/Integrations/`)

These folders contain standalone libraries that interface with external APIs (Google, Spotify, GitHub) and system utilities (clipboard, terminal, browser, process lists).

---

### 📆 Calendar (`src/CoreFunctions/Integrations/Calendar/`)

* **[calendar_service.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Calendar/calendar_service.py)**: Spawns authenticated calendar client objects.
* **[create_event.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Calendar/create_event.py)**: Adds items to calendars.
* **[read_event.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Calendar/read_event.py)**: Queries calendar timelines.

---

### 🎓 Classroom (`src/CoreFunctions/Integrations/Classroom/`)

* **[classroom_ops.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Classroom/classroom_ops.py)**: Retrieves courses, assignments, and announcements.
* **[classroom_file_ops.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Classroom/classroom_file_ops.py)**: Handles classroom file submission and downloads.

---

### ✉️ Gmail (`src/CoreFunctions/Integrations/Gmail/`)

* **[gmail_ops.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Gmail/gmail_ops.py)**: Core Gmail client wrapping reads, trashing, marking read, and replying.
* **[gmail_file_ops.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Gmail/gmail_file_ops.py)**: Processes email attachments.
* **[read_unread.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Gmail/read_unread.py)**: Legacy filter helpers.
* **[gmail_sender.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Gmail/gmail_sender.py)** / **[gmail_handler.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Gmail/gmail_handler.py)**: Legacy direct script integrations.

---

### 📊 System (`src/CoreFunctions/Integrations/System/`)

* **[system_actions.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/System/system_actions.py)**: Controls system actions (mute status, brightness levels, screen lock, media controllers).
* **[clipboard_ops.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/System/clipboard_ops.py)**: Interfaces with clipboards.
* **[download_ops.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/System/download_ops.py)**: Handles file downloads.
* **[system_monitor.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/System/system_monitor.py)**: Reads system specs.

---

### ⚙️ System Control (`src/CoreFunctions/Integrations/SystemControl/`)

* **[execution.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/SystemControl/execution.py)**: Command validation runner.

---

### 🎵 Spotify (`src/CoreFunctions/Integrations/Spotify/`)

* **[spotify_client.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Spotify/spotify_client.py)**: Spotify client library.

---

### 📋 Briefing (`src/CoreFunctions/Integrations/Briefing/`)

* **[briefing.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Briefing/briefing.py)**: Aggregates daily briefing content.

---

### 🚀 Automation (`src/CoreFunctions/Integrations/Automation/`)

* **[scheduler_ops.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Automation/scheduler_ops.py)**: Persistent task scheduler.

---

### 💻 GitHub (`src/CoreFunctions/Integrations/Github/`)

* **[github_ops.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Github/github_ops.py)**: GitHub operations.

---

### 🗂️ Classroom & Google Tasks (`src/CoreFunctions/Integrations/Classroom/`, `src/CoreFunctions/Integrations/Google/`)

* **[tasks.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/src/CoreFunctions/Integrations/Google/tasks.py)**: Google Tasks.

---

## 📜 4. Project Scripts (`scripts/`)

Standalone scripts for index generation, setup steps, migration, and scraping experiments.

* **[clear_skills.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/scripts/clear_skills.py)**: Clears skills database files.
* **[migrate_skills.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/scripts/migrate_skills.py)**: Organizes raw markdown skills into their respective folders.
* **[setup_ytmusic.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/scripts/setup_ytmusic.py)** / **[do_setup_ytmusic.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/scripts/do_setup_ytmusic.py)** / **[verify_ytmusic.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/scripts/verify_ytmusic.py)**: Sets up, updates, and verifies library integrations for YouTube Music.
* **[experiment_dom_tagging.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/scripts/browser_experiment/experiment_dom_tagging.py)** / **[experiment_markdown.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/scripts/browser_experiment/experiment_markdown.py)**: Experimental scraper parsing raw HTML trees into clean markdown tags.

---

## 🧪 5. Testing Suites (`tests/`)

Standard tests verifying execution layers, sandbox security, memory engines, and concurrent processes.

* **[test_sandbox_security.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/tests/test_sandbox_security.py)**: Asserts that path validation raises exceptions for directory traversals.
* **[test_parallel_inputs.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/tests/test_parallel_inputs.py)**: Simulates simultaneous CLI prompt interruptions to verify that the stdin lock behaves correctly.
* **[test_memory.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/tests/test_memory.py)** / **[test_skills.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/tests/test_skills.py)**: Validates indexing, updates, and queries for FAISS and JSON memory stores.
* **[test_browser_worker.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/tests/test_browser_worker.py)**: Verifies headless browser page interactions.
* **[test_classroom_visualizer.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/tests/test_classroom_visualizer.py)**: Tests Google Classroom assignment listing.
* **[test_new_tools.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/tests/test_new_tools.py)**: Tests credentials encryption and Clipboard operations.
* **[test_workers_config.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/tests/test_workers_config.py)**: Validates active/inactive filtering and custom LLM configurations loaded from config.
* **[test_database_memory.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/tests/test_database_memory.py)**: Validates SQLite database storage and transactions via UnifiedMemory.
* **[test_plug_and_play.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/tests/test_plug_and_play.py)**: Tests that scanned dynamic ReAct workers are successfully registered in the WorkerRegistry.
* **[test_registry.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/tests/test_registry.py)**: Validates decorator registration logic and configurations.
* **[test_live_reload.py](file:///home/prit/Project_Linux/AI-Personal-Assistant-Backend/tests/test_live_reload.py)**: Asserts reload/scanning loops dynamically sync changes.
