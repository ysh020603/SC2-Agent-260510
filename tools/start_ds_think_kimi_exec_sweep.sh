#!/usr/bin/env bash
# DeepSeek-V4-flash_think (naming/ordering) + Kimi-k2.5 (executor) hybrid sweep.
#
# Usage:
#   bash tools/start_ds_think_kimi_exec_sweep.sh
#
# Attach:
#   tmux attach -t ds_think_kimi_exec_sweep

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

SESSION="${TMUX_SESSION:-ds_think_kimi_exec_sweep}"
BATCH_NAME="${BATCH_NAME:-ds_think_kimi_exec_v7}"

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
  "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$BATCH_NAME") \
CONCURRENCY=$(printf '%q' "${CONCURRENCY:-5}") \
REPEATS=$(printf '%q' "${REPEATS:-1}") \
GAME_TIME_LIMIT=$(printf '%q' "${GAME_TIME_LIMIT:-1200}") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
NAMING_MODEL=$(printf '%q' "${NAMING_MODEL:-DeepSeek-V4-flash_think}") \
ORDERING_MODEL=$(printf '%q' "${ORDERING_MODEL:-DeepSeek-V4-flash_think}") \
EXECUTOR_MODEL=$(printf '%q' "${EXECUTOR_MODEL:-Kimi-k2.5}") \
DIFFICULTIES=$(printf '%q' "${DIFFICULTIES:-medium,mediumhard,hard,veryhard}") \
bash $(printf \'%q\' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"
echo "=================================================="
echo " Tmux session : $SESSION"
echo " Batch        : $BATCH_NAME"
echo " Naming       : DeepSeek-V4-flash_think"
echo " Ordering     : DeepSeek-V4-flash_think"
echo " Executor     : Kimi-k2.5"
echo " Difficulties : medium, mediumhard, hard, veryhard"
echo " Repeats      : 1 per matchup"
echo " Concurrency  : ${CONCURRENCY:-5}"
echo " Total jobs   : 216"
echo " Attach       : tmux attach -t $SESSION"
echo "=================================================="
