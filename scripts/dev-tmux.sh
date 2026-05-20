#!/usr/bin/env bash
set -e

SESSION="exchange"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmux kill-session -t "$SESSION" 2>/dev/null || true

tmux new-session -d -s "$SESSION" -c "$ROOT"

# Create 10 more panes (11 total), re-tile after each split
for _ in $(seq 10); do
    tmux split-window -t "$SESSION" -c "$ROOT"
    tmux select-layout -t "$SESSION" tiled
done
tmux select-layout -t "$SESSION" tiled

# Show pane title bar at the top of each pane border
tmux set-option -t "$SESSION" pane-border-status top
tmux set-option -t "$SESSION" pane-border-format "#{?pane_active,#[fg=red],} #{pane_title} #[default]"

# Pane layout (tiled):
# 0: postgres     1: account      2: notifications
# 3: risk         4: oms          5: clearing
# 6: matching     7: market-data  8: gateway
# 9: db-shell    10: shell

tmux select-pane -t "$SESSION:0.0"  -T "postgres"
tmux select-pane -t "$SESSION:0.1"  -T "account"
tmux select-pane -t "$SESSION:0.2"  -T "notifications"
tmux select-pane -t "$SESSION:0.3"  -T "risk-engine"
tmux select-pane -t "$SESSION:0.4"  -T "order-management"
tmux select-pane -t "$SESSION:0.5"  -T "clearing"
tmux select-pane -t "$SESSION:0.6"  -T "matching-engine"
tmux select-pane -t "$SESSION:0.7"  -T "market-data"
tmux select-pane -t "$SESSION:0.8"  -T "gateway"
tmux select-pane -t "$SESSION:0.9"  -T "db-shell"
tmux select-pane -t "$SESSION:0.10" -T "shell"

tmux send-keys -t "$SESSION:0.0"  "just infra-up" Enter
tmux send-keys -t "$SESSION:0.1"  "sleep 3 && just run-account" Enter
tmux send-keys -t "$SESSION:0.2"  "sleep 3 && just run-notifications" Enter
tmux send-keys -t "$SESSION:0.3"  "sleep 5 && just run-risk" Enter
tmux send-keys -t "$SESSION:0.4"  "sleep 5 && just run-oms" Enter
tmux send-keys -t "$SESSION:0.5"  "sleep 3 && just run-clearing" Enter
tmux send-keys -t "$SESSION:0.6"  "sleep 7 && just run-matching" Enter
tmux send-keys -t "$SESSION:0.7"  "sleep 3 && just run-market-data" Enter
tmux send-keys -t "$SESSION:0.8"  "sleep 7 && just run-gateway" Enter
tmux send-keys -t "$SESSION:0.9"  "sleep 3 && just db-shell" Enter

tmux attach-session -t "$SESSION"
