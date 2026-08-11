#!/usr/bin/env bash
# OLD-6 macro sweep:
#   naming/ordering = DeepSeek-V4-flash_think
#   executor        = Qwen3-32b_think
#
# Protocol: OLD-6, P/T/Z, macro, KairosJunctionLE,
#           difficulties=veryeasy,medium,hard (NO veryhard), repeats=5 -> 270 jobs
# Peak pause (Beijing): 09:00-12:00, 14:00-18:00 — no NEW jobs start.
#
# Usage:
#   bash tools/start_old6_ds_flash_think_exec32b_macro.sh
# Resume:
#   SKIP_COMPLETED=1 bash tools/start_old6_ds_flash_think_exec32b_macro.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

SESSION="${TMUX_SESSION:-old6_ds_flash_think_exec32b}"
BATCH_NAME="${BATCH_NAME:-ds_flash_think_order_exec32b_6old_macro_r5}"
CONCURRENCY="${CONCURRENCY:-15}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
DECISION_MODE="${DECISION_MODE:-three-stage}"
AUTO_EXIT="${AUTO_EXIT:-1}"
SKIP_COMPLETED="${SKIP_COMPLETED:-0}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"

STRATEGIES="${STRATEGIES:-banshees,battle_cruisers,bio,cyclones,marine_rush,two_base_tanks}"
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"

NAMING_MODEL="${NAMING_MODEL:-DeepSeek-V4-flash_think}"
ORDERING_MODEL="${ORDERING_MODEL:-DeepSeek-V4-flash_think}"
EXECUTOR_MODEL="${EXECUTOR_MODEL:-Qwen3-32b_think}"
PAUSE_HHMM_WINDOWS="${PAUSE_HHMM_WINDOWS:-09:00-12:00,14:00-18:00}"
PAUSE_TIMEZONE="${PAUSE_TIMEZONE:-Asia/Shanghai}"
SCHEDULE_BALANCE="${SCHEDULE_BALANCE:-difficulty,race}"

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Killing existing tmux session: $SESSION"
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  sleep 1
fi
pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${BATCH_NAME}" 2>/dev/null || true
pkill -f "run_experiment.py --batch-name ${BATCH_NAME} " 2>/dev/null || true
sleep 1

tmux new-session -d -s "$SESSION" -n sweep \
  "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$BATCH_NAME") \
CONCURRENCY=$(printf '%q' "$CONCURRENCY") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=0 \
SKIP_COMPLETED=$(printf '%q' "$SKIP_COMPLETED") \
AUTO_EXIT=$(printf '%q' "$AUTO_EXIT") \
MAX_ATTEMPTS=$(printf '%q' "$MAX_ATTEMPTS") \
NAMING_MODEL=$(printf '%q' "$NAMING_MODEL") \
ORDERING_MODEL=$(printf '%q' "$ORDERING_MODEL") \
EXECUTOR_MODEL=$(printf '%q' "$EXECUTOR_MODEL") \
DECISION_MODE=$(printf '%q' "$DECISION_MODE") \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
PAUSE_HHMM_WINDOWS=$(printf '%q' "$PAUSE_HHMM_WINDOWS") \
PAUSE_TIMEZONE=$(printf '%q' "$PAUSE_TIMEZONE") \
SCHEDULE_BALANCE=$(printf '%q' "$SCHEDULE_BALANCE") \
bash $(printf '%q' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"

echo "=================================================="
echo " DS-flash_think order + 32B_think exec (OLD-6)"
echo " Tmux     : ${SESSION}"
echo " Batch    : game_records/${BATCH_NAME}/"
echo " Naming   : ${NAMING_MODEL}"
echo " Ordering : ${ORDERING_MODEL}"
echo " Executor : ${EXECUTOR_MODEL}"
echo " Jobs     : 270 (no veryhard)"
echo " Concur   : ${CONCURRENCY}"
echo " Balance  : ${SCHEDULE_BALANCE}"
echo " Pause    : ${PAUSE_HHMM_WINDOWS} (${PAUSE_TIMEZONE})"
echo " Attach   : tmux attach -t ${SESSION}"
echo " Logs     : game_records/${BATCH_NAME}_stdout.log"
echo "=================================================="
