#!/usr/bin/env bash
# Start Qwen3-32B OLD-6 watchdog in a detached tmux session.
#
# Waits until http://172.18.30.162:8000 serves model qwen3-32b (and Kimi think
# is reachable), then launches:
#   - all_think   (conc=5)
#   - kimi_order  (conc=3)
#
# Usage:
#   bash tools/start_watchdog_qwen32b_old6.sh
#   WATCH_INTERVAL=30 SUCCESS_STREAK=2 bash tools/start_watchdog_qwen32b_old6.sh
#   bash tools/start_watchdog_qwen32b_old6.sh --once --dry-run
#   bash tools/start_watchdog_qwen32b_old6.sh --self-test

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

SESSION="${SESSION:-wd_qwen32b_old6}"
EXTRA_ARGS=("$@")

mkdir -p game_records/_watchdog

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  exec python3 "$SCRIPT_DIR/watchdog_qwen32b_old6_macro.py" "${EXTRA_ARGS[@]}"
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Killing existing tmux session: $SESSION"
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  sleep 1
fi

tmux new-session -d -s "$SESSION" -n watchdog \
  "cd $(printf '%q' "$ROOT") && \
WATCH_INTERVAL=$(printf '%q' "${WATCH_INTERVAL:-30}") \
SUCCESS_STREAK=$(printf '%q' "${SUCCESS_STREAK:-2}") \
SKIP_COMPLETED=$(printf '%q' "${SKIP_COMPLETED:-0}") \
python3 $(printf '%q' "$SCRIPT_DIR/watchdog_qwen32b_old6_macro.py"); \
echo '[watchdog exited]'; sleep 3600"

echo "=================================================="
echo " Watchdog started (Qwen3-32B OLD-6)"
echo " Tmux     : ${SESSION}"
echo " Interval : ${WATCH_INTERVAL:-30}s"
echo " Streak   : ${SUCCESS_STREAK:-2}"
echo " Wait for : qwen3-32b @ 172.18.30.162:8000 + Kimi think"
echo " Launch   : all_think(conc=5) + kimi_order(conc=3), no VH"
echo " Attach   : tmux attach -t ${SESSION}"
echo " Log      : game_records/_watchdog/qwen32b_old6.log"
echo " State    : game_records/_watchdog/qwen32b_old6.state.json"
echo "=================================================="
