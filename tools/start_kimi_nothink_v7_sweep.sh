#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

SESSION="${TMUX_SESSION:-kimi_nothink_v7_sweep}"
BATCH_NAME="${BATCH_NAME:-kimi_nothink_v7_strategies}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Tmux session already exists: $SESSION"
  echo "Attach: tmux attach -t $SESSION"
  exit 1
fi

pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${BATCH_NAME}" 2>/dev/null || true
pkill -f "run_experiment.py.*--batch-name ${BATCH_NAME}" 2>/dev/null || true
sleep 2

tmux new-session -d -s "$SESSION" -n sweep \
  "cd $(printf '%q' "$ROOT") && BATCH_NAME=$(printf '%q' "$BATCH_NAME") CONCURRENCY=$(printf '%q' "${CONCURRENCY:-3}") REPEATS=$(printf '%q' "${REPEATS:-2}") GAME_TIME_LIMIT=$(printf '%q' "${GAME_TIME_LIMIT:-1200}") START_INDEX=$(printf '%q' "${START_INDEX:-0}") bash $(printf \'%q\' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"
echo "=================================================="
echo " Tmux session : $SESSION"
echo " Batch        : $BATCH_NAME"
echo " Concurrency  : ${CONCURRENCY:-3}"
echo " Start index  : ${START_INDEX:-0}"
echo " Attach       : tmux attach -t $SESSION"
echo "=================================================="
