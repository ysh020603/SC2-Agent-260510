#!/usr/bin/env bash
# DS think (naming/ordering) + DS flash (executor), Terran opponents, Macro build.
# Single map: KairosJunctionLE
#
# Usage:
#   bash tools/start_ds_think_flash_exec_terran_macro_sweep.sh
#
# Attach:
#   tmux attach -t ds_think_flash_exec_terran_macro_sweep

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

SESSION="${TMUX_SESSION:-ds_think_flash_exec_terran_macro_sweep}"
BATCH_NAME="${BATCH_NAME:-ds_think_flash_exec_v7_terran_macro}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

tmux kill-session -t "$SESSION" 2>/dev/null || true
pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${BATCH_NAME}" 2>/dev/null || true
pkill -f "run_experiment.py.*--batch-name ${BATCH_NAME}" 2>/dev/null || true
sleep 2

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Tmux session still exists: $SESSION" >&2
  exit 1
fi

tmux new-session -d -s "$SESSION" -n sweep \
  "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$BATCH_NAME") \
CONCURRENCY=$(printf '%q' "${CONCURRENCY:-10}") \
REPEATS=$(printf '%q' "${REPEATS:-1}") \
GAME_TIME_LIMIT=$(printf '%q' "${GAME_TIME_LIMIT:-1200}") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
NAMING_MODEL=$(printf '%q' "${NAMING_MODEL:-DeepSeek-V4-flash_think}") \
ORDERING_MODEL=$(printf '%q' "${ORDERING_MODEL:-DeepSeek-V4-flash_think}") \
EXECUTOR_MODEL=$(printf '%q' "${EXECUTOR_MODEL:-DeepSeek-V4-flash}") \
DIFFICULTIES=$(printf '%q' "${DIFFICULTIES:-medium,mediumhard,hard,veryhard}") \
ENEMY_RACES=terran \
ENEMY_BUILD=macro \
MAPS=KairosJunctionLE \
bash $(printf \'%q\' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"
echo "=================================================="
echo " Tmux session      : $SESSION"
echo " Batch folder      : game_records/${BATCH_NAME}/"
echo " Map               : KairosJunctionLE only"
echo " Naming/Ordering   : DeepSeek-V4-flash_think"
echo " Executor          : DeepSeek-V4-flash (non-thinking)"
echo " Enemy             : terran only | build=macro"
echo " Difficulties      : medium, mediumhard, hard, veryhard"
echo " Supply managed    : off"
echo " Concurrency       : ${CONCURRENCY:-10}"
echo " Total jobs        : 24"
echo " Attach            : tmux attach -t $SESSION"
echo "=================================================="
