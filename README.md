# 🤖 AI Personal Assistant (Backend)

> **"LLMs decide, Code executes."**

A powerful, secure, and extensible local AI assistant designed to interact with your system, manage communications, and organize your digital life. Built with a modular **Multi-Agent Architecture**, it prioritizes safety and local execution while leveraging advanced LLMs for reasoning.

## 🚀 Project Overview

This project implements a sophisticated backend for an AI Personal Assistant. Unlike simple chatbots, this system is capable of performing real-world actions on your computer—managing files, checking system stats, sending WhatsApp messages, and controlling applications—all while adhering to a strict security policy.

### Key Philosophies

- **Safety First**: Critical actions (like file deletion or execution) are password-protected.
- **Modular Design**: Specialized agents handle specific domains (System, Communication, etc.).
- **Local Control**: Uses local tools and APIs (like WAHA for WhatsApp) to keep dependencies efficient.

## ✨ Current Features

- **🧠 Multi-Agent Orchestrator**

  - Intelligent request routing to specialized agents.
  - **Planner** agent breaks down complex user requests into executable steps.
  - **Agent Manager** coordinates execution.

    ```mermaid
    graph TD
        User[User Input] -->|1. Request| Manager[Agent Manager]
        Manager -->|2. Delegate| Planner[Planner Agent]
        Planner -->|3. Create Plan| Plan[Execution Plan]

        subgraph Execution Loop
            Plan -->|4. Next Step| Router{Agent Router}
            Router -->|Assign| AgentA[Specialized Agent]
            AgentA -->|5. Execute| Tools[Tools / API]
            Tools -->|6. Result| Manager
        end

        Manager -->|7. Loop/Finish| Plan
        Manager -->|8. Final Response| User

        style Manager fill:#f9f,stroke:#333
        style Planner fill:#bbf,stroke:#333
        style AgentA fill:#dfd,stroke:#333
    ```

- **🔌 Integrations**

  - **WhatsApp**: Full sending/receiving capabilities via [WAHA](https://waha.devlike.pro/).
  - **System Control**: Check CPU/RAM usage, launch applications, and manage processes.
  - **File Operations**: Safe read/write/list capabilities within a sandboxed environment.
  - **Spotify**: Basic playback control (launch and interaction).
  - **Google Services**: Calendar and Gmail integration points.

- **🛡️ Security**
  - `.env` based secrets management.
  - Password verification hook for high-risk tools.

## 🛠️ Architecture

```text
src/
├── CoreFunctions/  # The "Brain" (Orchestrator, Tools Registry, Memory)
└── Apps/           # The "Hands" (WhatsApp, System, FileOperations, Spotify)
```

## 🏁 Getting Started

### Prerequisites

- Python 3.10+
- Docker (for WAHA Service)
- Google Gemini API Key (current LLM provider)

### Installation

1.  **Clone the repository**

    ```bash
    git clone https://github.com/yourusername/AI-Personal-Assistant-Backend.git
    cd AI-Personal-Assistant-Backend
    ```

2.  **Set up Virtual Environment**

    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Linux/Mac
    source .venv/bin/activate
    ```

3.  **Install Dependencies**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration**
    Create a `.env` file in the root directory:

    ```ini
    GEMINI_API_KEY=your_api_key
    SYSTEM_PASSWORD=your_secure_password
    ```

5.  **Start Services (WhatsApp)**
    ```bash
    docker-compose up -d
    # Scan QR code at http://localhost:3000/dashboard
    ```

### Usage

Run the multi-agent orchestrator:

```bash
python src/CoreFunctions/multi_agent.py
```

## 🗺️ Roadmap & Future Goals

This project is actively evolving. Our current focus is on stability and offline independence.

- [ ] **Full Offline Capability**: Replace Cloud LLMs (Gemini) with local quantized models (e.g., Llama 3, Gemma 2 via Ollama) for complete privacy.
- [ ] **Enhanced GUI**: Build a proper frontend dashboard for monitoring agent state and chat.
- [ ] **Voice Interface**: Add Speech-to-Text (Whisper) and Text-to-Speech execution.
- [ ] **Smart Context**: Improve vector memory implementation for better long-term recall of user preferences.
- [ ] **Expanded App Ecosystem**: Deepen integration with Spotify, Notion, and generic OS automation.

## 🤝 Contributing

Contributions are welcome! Please check out the `PROJECT_DOCUMENTATION.md` for deep technical details before submitting a Pull Request.

---

_Created with ❤️ by the AI Personal Assistant Team_
