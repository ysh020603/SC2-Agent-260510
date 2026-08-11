#!/usr/bin/env bash
# Start balanced-nocot OLD-6 watchdog in a detached tmux session.
#
# Waits until BOTH endpoints serve the expected model ids and pass chat probe:
#   :8010  qwen3-1.7b-our-balanced-nocot-stage1
#   :8011  qwen3-1.7b-our-balanced-nocot-mix-grpo-v2-nothink
# then launches two OLD-6 sweeps (conc=20 each, thinking OFF).
#
# Usage:
#   bash tools/start_watchdog_balanced_nocot_old6.sh
#   WATCH_INTERVAL=30 SUCCESS_STREAK=2 bash tools/start_watchdog_balanced_nocot_old6.sh
#   bash tools/start_watchdog_balanced_nocot_old6.sh --once --dry-run
#   bash tools/start_watchdog_balanced_nocot_old6.sh --self-test

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

SESSION="${SESSION:-wd_balanced_nocot_old6}"
EXTRA_ARGS=("$@")

mkdir -p game_records/_watchdog

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  exec python3 "$SCRIPT_DIR/watchdog_balanced_nocot_old6_macro.py" "${EXTRA_ARGS[@]}"
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Killing existing tmux session: $SESSION"
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  sleep 1
fi

# Clear previous launched state so a fresh deploy can trigger.
rm -f game_records/_watchdog/balanced_nocot_old6.state.json

tmux new-session -d -s "$SESSION" -n watchdog \
  "cd $(printf '%q' "$ROOT") && \
WATCH_INTERVAL=$(printf '%q' "${WATCH_INTERVAL:-30}") \
SUCCESS_STREAK=$(printf '%q' "${SUCCESS_STREAK:-2}") \
SKIP_COMPLETED=$(printf '%q' "${SKIP_COMPLETED:-0}") \
CONCURRENCY=$(printf '%q' "${CONCURRENCY:-20}") \
python3 $(printf '%q' "$SCRIPT_DIR/watchdog_balanced_nocot_old6_macro.py"); \
echo '[watchdog exited]'; sleep 3600"

echo "=================================================="
echo " Watchdog started (balanced nocot OLD-6)"
echo " Tmux     : ${SESSION}"
echo " Interval : ${WATCH_INTERVAL:-30}s"
echo " Streak   : ${SUCCESS_STREAK:-2}"
echo " Wait for : stage1 @ :8010 + mix-grpo-v2 @ :8011"
echo " Launch   : 2x OLD-6 (conc=${CONCURRENCY:-20}, nothink, no VH)"
echo " Attach   : tmux attach -t ${SESSION}"
echo " Log      : game_records/_watchdog/balanced_nocot_old6.log"
echo " State    : game_records/_watchdog/balanced_nocot_old6.state.json"
echo "=================================================="
