#!/usr/bin/env bash
# Start the v2a2048 OLD-6 watchdog inside a detached tmux session.
#
# Usage:
#   bash tools/start_watchdog_v2a2048_old6.sh
#   WATCH_INTERVAL=30 SUCCESS_STREAK=2 bash tools/start_watchdog_v2a2048_old6.sh
#   bash tools/start_watchdog_v2a2048_old6.sh --once --dry-run
#
# Env:
#   WATCH_INTERVAL   poll seconds (default 60)
#   SUCCESS_STREAK   consecutive healthy polls before launch (default 2)
#   READY_MODE       all|each (default all)
#   CONCURRENCY      sweep concurrency (default 8)
#   SKIP_COMPLETED   0|1
#   SESSION          tmux session name (default wd_v2a2048_old6)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

SESSION="${SESSION:-wd_v2a2048_old6}"
EXTRA_ARGS=("$@")

mkdir -p game_records/_watchdog

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

# If caller passes flags, run foreground (useful for --once / --self-test / --dry-run)
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  exec python3 "$SCRIPT_DIR/watchdog_v2a2048_old6_macro.py" "${EXTRA_ARGS[@]}"
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Killing existing tmux session: $SESSION"
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  sleep 1
fi

tmux new-session -d -s "$SESSION" -n watchdog \
  "cd $(printf '%q' "$ROOT") && \
WATCH_INTERVAL=$(printf '%q' "${WATCH_INTERVAL:-60}") \
SUCCESS_STREAK=$(printf '%q' "${SUCCESS_STREAK:-2}") \
READY_MODE=$(printf '%q' "${READY_MODE:-all}") \
CONCURRENCY=$(printf '%q' "${CONCURRENCY:-8}") \
SKIP_COMPLETED=$(printf '%q' "${SKIP_COMPLETED:-0}") \
python3 $(printf '%q' "$SCRIPT_DIR/watchdog_v2a2048_old6_macro.py"); \
echo '[watchdog exited]'; sleep 3600"

echo "=================================================="
echo " Watchdog started"
echo " Tmux     : ${SESSION}"
echo " Interval : ${WATCH_INTERVAL:-60}s"
echo " Streak   : ${SUCCESS_STREAK:-2}"
echo " Mode     : ${READY_MODE:-all}"
echo " Attach   : tmux attach -t ${SESSION}"
echo " Log      : game_records/_watchdog/v2a2048_old6.log"
echo " State    : game_records/_watchdog/v2a2048_old6.state.json"
echo "=================================================="
