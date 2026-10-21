#!/usr/bin/env bash
# ==============================================================================
# launch_assistant.sh: Unified Launcher for AI Personal Assistant & Telegram Bot
# Location: /home/prit/Project_Linux/AI-Personal-Assistant-Backend/scripts/launch_assistant.sh
# ==============================================================================

set -euo pipefail

BACKEND_DIR="/home/prit/Project_Linux/AI-Personal-Assistant-Backend"
PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
TELEGRAM_SCRIPT="$BACKEND_DIR/run_telegram.py"
MODULAR_SCRIPT="$BACKEND_DIR/run_modular.py"
CLI_SCRIPT="$BACKEND_DIR/run_cli.py"
LOG_DIR="$BACKEND_DIR/Memory/logs"
TELEGRAM_LOG="$LOG_DIR/telegram.log"
TELEGRAM_PID_FILE="$LOG_DIR/telegram.pid"

WINDOW_TITLE="AI Personal Assistant"
WINDOW_CLASS="ai-personal-assistant"

START_TELEGRAM=true
KEEP_TELEGRAM=false
RUN_TARGET="$MODULAR_SCRIPT"
OVERRIDE_TERM=""
INTERNAL_RUN=false
EXTRA_ARGS=()

show_help() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] [--] [ASSISTANT_ARGS...]

Unified launcher for AI Personal Assistant and Telegram Remote Gateway.
Opens the interactive assistant in a separate terminal window and launches
the Telegram Gateway bot.

Options:
  --no-telegram          Do not start the Telegram bot gateway
  --keep-telegram        Keep Telegram bot running in background after terminal closes
  --telegram-only        Start Telegram bot in background without opening terminal assistant
  --stop-telegram        Stop any currently running Telegram bot instance
  --status               Show running status of Assistant and Telegram bot
  --cli                  Launch legacy pure CLI (run_cli.py) instead of modular pipeline
  -t, --term <TERM>      Override terminal emulator (default: auto-detected, prefers kitty)
  -T, --title <TITLE>    Override terminal window title
  -h, --help             Show this help message

Examples:
  assistant-term                   # Opens modular assistant + Telegram in Kitty
  assistant-term --keep-telegram   # Telegram stays active even after closing terminal
  assistant-term --no-telegram     # Open assistant terminal only
  assistant-term --status          # Check if Telegram bot is currently running
  assistant-term --stop-telegram   # Stop background Telegram bot
EOF
}

# Helper: Get running Telegram PID if any
get_telegram_pid() {
    if [[ -f "$TELEGRAM_PID_FILE" ]]; then
        local pid
        pid="$(cat "$TELEGRAM_PID_FILE" 2>/dev/null || true)"
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return 0
        fi
    fi
    # Fallback search by process command line
    pgrep -f "$TELEGRAM_SCRIPT" 2>/dev/null | head -n 1 || true
}

# Subcommand: Status
cmd_status() {
    echo "=== AI Personal Assistant Status ==="
    echo "Backend Directory: $BACKEND_DIR"
    local tg_pid
    tg_pid="$(get_telegram_pid)"
    if [[ -n "$tg_pid" ]]; then
        echo "📱 Telegram Gateway: RUNNING (PID: $tg_pid)"
        echo "   Logs: $TELEGRAM_LOG"
    else
        echo "📱 Telegram Gateway: STOPPED"
    fi

    local asst_pids
    asst_pids="$(pgrep -f "$MODULAR_SCRIPT" 2>/dev/null || true)"
    if [[ -n "$asst_pids" ]]; then
        echo "🤖 Modular Assistant: RUNNING (PID(s): $(echo "$asst_pids" | tr '\n' ' '))"
    else
        echo "🤖 Modular Assistant: STOPPED"
    fi
    exit 0
}

# Subcommand: Stop Telegram
cmd_stop_telegram() {
    local tg_pid
    tg_pid="$(get_telegram_pid)"
    if [[ -z "$tg_pid" ]]; then
        echo "Telegram Gateway is not currently running."
        rm -f "$TELEGRAM_PID_FILE"
        exit 0
    fi
    echo "Stopping Telegram Gateway (PID: $tg_pid)..."
    kill "$tg_pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$tg_pid" 2>/dev/null; then
        kill -9 "$tg_pid" 2>/dev/null || true
    fi
    rm -f "$TELEGRAM_PID_FILE"
    echo "✔ Telegram Gateway stopped."
    exit 0
}

# Subcommand: Telegram Only
cmd_telegram_only() {
    mkdir -p "$LOG_DIR"
    local tg_pid
    tg_pid="$(get_telegram_pid)"
    if [[ -n "$tg_pid" ]]; then
        echo "⚠️  Telegram Gateway is already running (PID: $tg_pid)."
        echo "Logs: $TELEGRAM_LOG"
        exit 0
    fi

    echo "🚀 Starting Telegram Gateway in background..."
    nohup "$PYTHON_BIN" "$TELEGRAM_SCRIPT" >> "$TELEGRAM_LOG" 2>&1 &
    local new_pid=$!
    echo "$new_pid" > "$TELEGRAM_PID_FILE"
    sleep 1
    if kill -0 "$new_pid" 2>/dev/null; then
        echo "✔ Telegram Gateway running (PID: $new_pid)."
        echo "  Logs: tail -f $TELEGRAM_LOG"
    else
        echo "❌ Telegram Gateway failed to start. Check logs at $TELEGRAM_LOG"
        exit 1
    fi
    exit 0
}

# Parse command line options
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        --status)
            cmd_status
            ;;
        --stop-telegram)
            cmd_stop_telegram
            ;;
        --telegram-only)
            cmd_telegram_only
            ;;
        --no-telegram)
            START_TELEGRAM=false
            shift
            ;;
        --keep-telegram)
            KEEP_TELEGRAM=true
            shift
            ;;
        --cli)
            RUN_TARGET="$CLI_SCRIPT"
            shift
            ;;
        -t|--term)
            OVERRIDE_TERM="$2"
            shift 2
            ;;
        -T|--title)
            WINDOW_TITLE="$2"
            shift 2
            ;;
        --internal-terminal-run)
            # Internal flag passed when executing inside the spawned terminal window
            INTERNAL_RUN=true
            shift
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do
                EXTRA_ARGS+=("$1")
                shift
            done
            break
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

# Ensure Python venv exists
if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Error: Python venv not found at $PYTHON_BIN" >&2
    exit 1
fi

mkdir -p "$LOG_DIR"

# ------------------------------------------------------------------------------
# INTERNAL RUNNER (Executes INSIDE the separate terminal window)
# ------------------------------------------------------------------------------
if [[ "$INTERNAL_RUN" = true ]]; then
    cd "$BACKEND_DIR"

    SPAWNED_TG_PID=""
    cleanup() {
        if [[ "$KEEP_TELEGRAM" != true && -n "$SPAWNED_TG_PID" ]]; then
            if kill -0 "$SPAWNED_TG_PID" 2>/dev/null; then
                echo ""
                echo "🛑 Stopping Telegram Gateway (PID: $SPAWNED_TG_PID)..."
                kill "$SPAWNED_TG_PID" 2>/dev/null || true
                rm -f "$TELEGRAM_PID_FILE"
            fi
        fi
    }
    trap cleanup EXIT INT TERM HUP

    echo "============================================================"
    echo "  🤖 Starting AI Personal Assistant Environment"
    echo "  📁 Workspace: $BACKEND_DIR"

    if [[ "$START_TELEGRAM" = true ]]; then
        EXISTING_TG_PID="$(get_telegram_pid)"
        if [[ -n "$EXISTING_TG_PID" ]]; then
            echo "  📱 Telegram Gateway: Already active (PID: $EXISTING_TG_PID)"
        else
            echo "  📱 Telegram Gateway: Starting background daemon..."
            "$PYTHON_BIN" "$TELEGRAM_SCRIPT" >> "$TELEGRAM_LOG" 2>&1 &
            SPAWNED_TG_PID=$!
            echo "$SPAWNED_TG_PID" > "$TELEGRAM_PID_FILE"
            sleep 1
            if kill -0 "$SPAWNED_TG_PID" 2>/dev/null; then
                echo "  ✔ Telegram Gateway: Connected (PID: $SPAWNED_TG_PID)"
                echo "  📝 Telegram Logs: Memory/logs/telegram.log"
            else
                echo "  ⚠️  Telegram Gateway failed to start (check Memory/logs/telegram.log)"
                SPAWNED_TG_PID=""
            fi
        fi
    else
        echo "  📱 Telegram Gateway: Disabled (--no-telegram)"
    fi
    echo "============================================================"
    echo ""

    # Execute assistant REPL
    "$PYTHON_BIN" "$RUN_TARGET" "${EXTRA_ARGS[@]}"
    EXIT_CODE=$?

    if [[ $EXIT_CODE -ne 0 ]]; then
        echo ""
        echo "Assistant exited with code $EXIT_CODE. Press Enter to close window..."
        read -r _
    fi

    exit $EXIT_CODE
fi

# ------------------------------------------------------------------------------
# EXTERNAL LAUNCHER (Detects terminal and spawns detached window)
# ------------------------------------------------------------------------------
detect_terminal() {
    if [[ -n "$OVERRIDE_TERM" ]]; then
        if command -v "$OVERRIDE_TERM" >/dev/null 2>&1; then
            echo "$OVERRIDE_TERM"
            return 0
        else
            echo "Error: Specified terminal '$OVERRIDE_TERM' not found." >&2
            return 1
        fi
    fi

    if [[ -n "${TERMINAL:-}" ]] && command -v "$TERMINAL" >/dev/null 2>&1; then
        echo "$TERMINAL"
        return 0
    fi

    for term in kitty alacritty foot ghostty wezterm gnome-terminal konsole xfce4-terminal xterm; do
        if command -v "$term" >/dev/null 2>&1; then
            echo "$term"
            return 0
        fi
    done

    echo "Error: No supported terminal emulator detected." >&2
    return 1
}

TERM_BIN="$(detect_terminal)"
TERM_NAME="$(basename "$TERM_BIN")"

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

# Build internal execution arguments
RUN_ARGS=("$SCRIPT_PATH" "--internal-terminal-run")
if [[ "$START_TELEGRAM" = false ]]; then
    RUN_ARGS+=("--no-telegram")
fi
if [[ "$KEEP_TELEGRAM" = true ]]; then
    RUN_ARGS+=("--keep-telegram")
fi
if [[ "$RUN_TARGET" == "$CLI_SCRIPT" ]]; then
    RUN_ARGS+=("--cli")
fi
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    RUN_ARGS+=("--" "${EXTRA_ARGS[@]}")
fi

if [[ "$TERM_NAME" == "kitty" ]]; then
    kitty --detach --class "$WINDOW_CLASS" -T "$WINDOW_TITLE" -d "$BACKEND_DIR" bash "${RUN_ARGS[@]}"
    echo "🚀 Launched AI Personal Assistant + Telegram Gateway in a separate kitty window."
    exit 0
fi

TERM_CMD=()
case "$TERM_NAME" in
    alacritty)
        TERM_CMD=(alacritty --class "$WINDOW_CLASS,$WINDOW_CLASS" -T "$WINDOW_TITLE" --working-directory "$BACKEND_DIR" -e bash "${RUN_ARGS[@]}")
        ;;
    foot)
        TERM_CMD=(foot --app-id="$WINDOW_CLASS" -T "$WINDOW_TITLE" -D "$BACKEND_DIR" bash "${RUN_ARGS[@]}")
        ;;
    ghostty)
        TERM_CMD=(ghostty --title="$WINDOW_TITLE" --working-directory="$BACKEND_DIR" -e bash "${RUN_ARGS[@]}")
        ;;
    wezterm)
        TERM_CMD=(wezterm start --class "$WINDOW_CLASS" --cwd "$BACKEND_DIR" bash "${RUN_ARGS[@]}")
        ;;
    gnome-terminal)
        TERM_CMD=(gnome-terminal --title="$WINDOW_TITLE" --working-directory="$BACKEND_DIR" -- bash "${RUN_ARGS[@]}")
        ;;
    konsole)
        TERM_CMD=(konsole --workdir "$BACKEND_DIR" -e bash "${RUN_ARGS[@]}")
        ;;
    *)
        TERM_CMD=("$TERM_BIN" -e bash "${RUN_ARGS[@]}")
        ;;
esac

setsid "${TERM_CMD[@]}" >/dev/null 2>&1 &
echo "🚀 Launched AI Personal Assistant + Telegram Gateway in a separate $TERM_NAME window."
