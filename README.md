# AI Personal Assistant

## Running with Docker (Recommended for Safety)

Running the assistant in a Docker container isolates it from your main file system, ensuring it can only modify files within the allowed directories (like `Memory`).

### Prerequisites

- Docker and Docker Compose installed.

### Quick Start

1.  Ensure your `.env` file is set up with necessary keys.
2.  Run the following command in this directory:
    ```bash
    docker-compose up --build
    ```
3.  The API will be available at `http://localhost:5000`.

### Data Persistence

The `Memory` folder is mounted to the container, so any long-term memories or files created there will persist on your host machine even after the container stops.

---

# Phase 1: Local Python bot
