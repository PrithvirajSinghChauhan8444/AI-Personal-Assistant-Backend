#!/usr/bin/env bash
# ==============================================================================
# Script: split_council_tmux.sh
# Purpose: Dynamically monitors active Council Agent files in tmux.
#          Whenever a NEW agent is summoned / creates a new file, it
#          AUTOMATICALLY splits a new pane, attaches a title banner,
#          and rebalances the grid layout (tiled)!
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSIONS_DIR="$PROJECT_ROOT/Memory/research_reports/extreme_sessions"

if [ ! -d "$SESSIONS_DIR" ]; then
    echo "⚠️ No extreme sessions directory found yet ($SESSIONS_DIR)."
    exit 1
fi

LATEST_SESSION=$(ls -td "$SESSIONS_DIR"/session_* 2>/dev/null | head -n 1)

if [ -z "$LATEST_SESSION" ]; then
    echo "⚠️ No active council sessions found in $SESSIONS_DIR."
    exit 1
fi

echo "📁 Monitoring Active Council Session: $(basename "$LATEST_SESSION")"

# Check if running inside tmux
if [ -z "$TMUX" ]; then
    echo "ℹ️ Launching dedicated tmux session 'council_live'..."
    tmux new-session -s council_live "$0"
    exit 0
fi

# Enable pane title display on the top border of each pane
tmux set -w pane-border-status top
tmux set -w pane-border-format " #[bold,fg=cyan] [🔬 #{pane_title}] #[default] "

# Helper to build the command with a prominent colored banner + pane title + tail
build_tail_cmd() {
    local target_file="$1"
    local fname="$(basename "$target_file")"
    echo "printf '\033]2;%s\033\\\\' '$fname'; echo -e '\033[1;34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m'; echo -e ' \033[1;32m🔬 COUNCIL AGENT REPORT:\033[0m \033[1;37m$fname\033[0m'; echo -e '\033[1;34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m\n'; tail -n +1 -f '$target_file'"
}

# Keep track of handled files
declare -A HANDLED_FILES
MAIN_PANE="$TMUX_PANE"

echo "👀 Watching for Council Agents in $(basename "$LATEST_SESSION")..."

# Reactive Daemon Loop: Watches for new agent files continuously
while true; do
    NEW_FOUND=0
    for f in "$LATEST_SESSION"/0*.md; do
        if [ -f "$f" ] && [ -z "${HANDLED_FILES["$f"]}" ]; then
            HANDLED_FILES["$f"]=1
            NEW_FOUND=1
            FNAME="$(basename "$f")"
            echo "✨ [New Agent Detected] Summoning pane for $FNAME..."
            
            PANE_CMD=$(build_tail_cmd "$f")
            tmux split-window -t "$MAIN_PANE" -d "bash -c \"$PANE_CMD\""
        fi
    done

    # If any new pane was spawned, re-balance the entire grid layout automatically
    if [ "$NEW_FOUND" -eq 1 ]; then
        tmux select-layout -t "$MAIN_PANE" tiled
    fi

    sleep 1.5
done
