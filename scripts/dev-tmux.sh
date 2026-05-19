#!/usr/bin/env bash
set -e

SESSION="exchange"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmux kill-session -t "$SESSION" 2>/dev/null || true

tmux new-session -d -s "$SESSION" -c "$ROOT"

# Create 8 more panes (9 total), re-tile after each split
for _ in $(seq 8); do
    tmux split-window -t "$SESSION" -c "$ROOT"
    tmux select-layout -t "$SESSION" tiled
done
tmux select-layout -t "$SESSION" tiled

# Show pane title bar at the top of each pane border
tmux set-option -t "$SESSION" pane-border-status top
tmux set-option -t "$SESSION" pane-border-format " #{pane_title} "

# Pane layout (tiled, 3 rows × 3 cols on a wide terminal):
# 0: postgres     1: risk         2: oms
# 3: matching     4: clearing     5: market-data
# 6: gateway      7: db-shell     8: shell

tmux select-pane -t "$SESSION:0.0" -T "postgres"
tmux select-pane -t "$SESSION:0.1" -T "risk-engine"
tmux select-pane -t "$SESSION:0.2" -T "order-management"
tmux select-pane -t "$SESSION:0.3" -T "matching-engine"
tmux select-pane -t "$SESSION:0.4" -T "clearing"
tmux select-pane -t "$SESSION:0.5" -T "market-data"
tmux select-pane -t "$SESSION:0.6" -T "gateway"
tmux select-pane -t "$SESSION:0.7" -T "db-shell"
tmux select-pane -t "$SESSION:0.8" -T "shell"

tmux send-keys -t "$SESSION:0.0" "just infra-up" Enter
tmux send-keys -t "$SESSION:0.1" "sleep 3 && just run-risk" Enter
tmux send-keys -t "$SESSION:0.2" "sleep 3 && just run-oms" Enter
tmux send-keys -t "$SESSION:0.3" "sleep 3 && just run-matching" Enter
tmux send-keys -t "$SESSION:0.4" "sleep 3 && just run-clearing" Enter
tmux send-keys -t "$SESSION:0.5" "sleep 3 && just run-market-data" Enter
tmux send-keys -t "$SESSION:0.6" "sleep 3 && just run-gateway" Enter
tmux send-keys -t "$SESSION:0.7" "sleep 3 && just db-shell" Enter

tmux attach-session -t "$SESSION"
