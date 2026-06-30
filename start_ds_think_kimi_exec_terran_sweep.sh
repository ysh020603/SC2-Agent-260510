#!/usr/bin/env bash
# DeepSeek think (naming/ordering) + Kimi exec — Terran opponents only.
# Single map: KairosJunctionLE
#
# Usage:
#   bash start_ds_think_kimi_exec_terran_sweep.sh
#
# Attach:
#   tmux attach -t ds_think_kimi_exec_terran_sweep

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

SESSION="${TMUX_SESSION:-ds_think_kimi_exec_terran_sweep}"
BATCH_NAME="${BATCH_NAME:-ds_think_kimi_exec_v7_terran}"

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
CONCURRENCY=$(printf '%q' "${CONCURRENCY:-5}") \
REPEATS=$(printf '%q' "${REPEATS:-1}") \
GAME_TIME_LIMIT=$(printf '%q' "${GAME_TIME_LIMIT:-1200}") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
NAMING_MODEL=$(printf '%q' "${NAMING_MODEL:-DeepSeek-V4-flash_think}") \
ORDERING_MODEL=$(printf '%q' "${ORDERING_MODEL:-DeepSeek-V4-flash_think}") \
EXECUTOR_MODEL=$(printf '%q' "${EXECUTOR_MODEL:-Kimi-k2.5}") \
DIFFICULTIES=$(printf '%q' "${DIFFICULTIES:-medium,mediumhard,hard,veryhard}") \
ENEMY_RACES=terran \
MAPS=KairosJunctionLE \
bash tools/run_strategy_sweep_tmux.sh"

echo "=================================================="
echo " Tmux session      : $SESSION"
echo " Batch folder      : game_records/${BATCH_NAME}/"
echo " Map               : KairosJunctionLE only"
echo " Naming/Ordering   : DeepSeek-V4-flash_think"
echo " Executor          : Kimi-k2.5"
echo " Enemy             : terran only | build=random"
echo " Difficulties      : medium, mediumhard, hard, veryhard"
echo " Concurrency       : ${CONCURRENCY:-5}"
echo " Total jobs        : 24"
echo " Attach            : tmux attach -t $SESSION"
echo "=================================================="
