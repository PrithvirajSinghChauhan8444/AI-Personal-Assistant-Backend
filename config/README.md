# Configuration Directory (`config/`)

This directory contains all user-configurable parameters for the AI Personal Assistant Backend.

---

## 1. Environment & Secrets (`.env` and `.env.example`)

The master configuration for API keys, model selections, and external ports:

| Variable | Description | Example / Default |
| :--- | :--- | :--- |
| `DEFAULT_MODEL` | Default model identifier across all agents. Supports provider prefixes. | `google:gemini-3.5-flash-lite`, `openai:gpt-4o`, `anthropic:claude-3-7-sonnet-20250219`, `ollama:llama3.2` |
| `GEMINI_API_KEY` | Google Gemini API key. | `AIzaSy...` |
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o / o-series. | `sk-...` |
| `ANTHROPIC_API_KEY`| Anthropic API key for Claude 3.5 / 3.7. | `sk-ant-...` |
| `GROQ_API_KEY` | Groq API key for high-speed inference. | `gsk_...` |
| `OLLAMA_HOST` | Endpoint for local offline Ollama models. | `http://localhost:11434` |
| `OLLAMA_MODEL` | Default local Ollama model. | `llama3.2`, `gemma4:e2b`, `qwen2.5-coder` |
| `SYSTEM_PASSWORD` | Password required to authorize destructive system actions. | `1234` |
| `TELEGRAM_BOT_TOKEN` | Token for Telegram Bot integration. | `8897267617:...` |
| `TELEGRAM_ALLOWED_USER_IDS` | Comma-separated list of Telegram User IDs allowed to access the bot. | `1909188006` |
| `BROWSER_CDP_URL` | Chrome DevTools Protocol port to attach to existing browser. | `http://localhost:9222` |
| `BROWSER_HEADLESS` | Whether browser runs headlessly. | `false` |

---

## 2. Specialist Agents Configuration (`config/agents.json`)

Configure models, temperatures, and concurrency settings individually for each agent:

- **`manager`**: The Layer 2 Cognitive Planner that decomposes user goals into DAG execution plans.
  - `model`: Model to use for DAG decomposition.
  - `temperature`: Low temperature (e.g. `0.1`) recommended for reliable JSON DAG generation.
  - `max_parallel_workers`: Maximum number of subtasks to dispatch concurrently in Go (default: `4`).
  - `auto_heal_deadlocks`: Automatically aborts blocked tasks if dependencies deadlock (`true`).
- **`system`**: Linux OS, files, process management, and git.
- **`browser`**: Playwright browser navigation, form filling, and screenshots.
- **`research`**: Web searches, fact-checking, and memory notes.
- **`productivity`**: Gmail triage, Google Calendar events.

---

## 3. Tool Safety & HITL Policies (`config/safety_policies.json`)

Controls the **Layer 2 Safety Gatekeeper**:
- **`risk`**:
  - `LOW`: Read-only actions (`fs_read`, `net_search`, `gmail_list`, `calendar_list`). Executed immediately.
  - `MEDIUM`: Non-destructive modifications (`fs_write`, `gmail_send_draft`).
  - `HIGH`: Destructive or external actions (`fs_delete`, `sys_exec`, `sys_kill`, `git_commit`).
- **`requires_interactive`**:
  - `true`: Completely blocked when running in background autonomous mode (cron/watchers) to prevent unauthorized prompt injection attacks. Requires interactive Human-In-The-Loop approval.
- **`required_capability`**: The permission capability required in the request scope.

---

## 4. System Settings (`config/system.json`)

- `user_id`: Default user identity (`local:prit`).
- `timezone`: Timezone for relative time parsing and Google Calendar (`Asia/Kolkata`).
- `log_level`: `DEBUG`, `INFO`, `WARN`, `ERROR`.
- `max_turn_iterations`: Maximum ReAct iterations allowed per turn (default: `10`).
- `artifact_spillover_threshold_bytes`: Payload limit (default: `102400` = 100KB) before spilling to disk (`workspace/artifacts/`).
- `database_path`: Location of SQLite session store (`workspace/data/sessions.db`).

---

## 5. Account & Identity Aliases (`config/accounts.json`)

Maps human-readable account aliases to specific email addresses:
```json
{
  "primary": "prithvirajsinghchauhan8444@gmail.com",
  "personal": "prithvirajsinghchauhan8444@gmail.com",
  "college": "prithvi24101@iiitnr.edu.in"
}
```
Allows prompts like *"Check my college emails"* vs *"Draft a message from my personal account"*.

---

## 6. Speech & Neural TTS (`config/speech.json`)

- `engine`: Primary TTS engine (`kokoro` or `piper`).
- `voice_kokoro`: Default Kokoro neural voice (e.g. `am_michael`).
- `voice_piper`: Default Piper ONNX voice file (`en_US-lessac-medium.onnx`).
- `sample_rate_hz`: `24000` (Kokoro) or `22050` (Piper).
