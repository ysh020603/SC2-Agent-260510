#!/usr/bin/env bash
# OLD-6 macro sweep: DeepSeek-V4-flash (non-thinking) for naming/ordering/executor.
#
# Protocol: OLD-6 strategies, P/T/Z, macro, KairosJunctionLE,
#           difficulties=veryeasy,medium,hard (NO veryhard), repeats=5
#           -> 6 * 3 * 3 * 5 = 270 jobs
# Concurrency: 20
# Peak pause (Beijing): 09:00-12:00 and 14:00-18:00 — no NEW jobs start.
#   (in-flight games may finish across the boundary)
#
# Usage:
#   bash tools/start_old6_deepseek_flash_nothink_macro.sh
# Resume:
#   SKIP_COMPLETED=1 bash tools/start_old6_deepseek_flash_nothink_macro.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

SESSION="${TMUX_SESSION:-old6_ds_flash_nothink}"
BATCH_NAME="${BATCH_NAME:-ds_flash_nothink_6old_macro_r5}"
CONCURRENCY="${CONCURRENCY:-20}"
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

MODEL_KEY="${MODEL_KEY:-DeepSeek-V4-flash}"
PAUSE_HHMM_WINDOWS="${PAUSE_HHMM_WINDOWS:-09:00-12:00,14:00-18:00}"
PAUSE_TIMEZONE="${PAUSE_TIMEZONE:-Asia/Shanghai}"

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
NAMING_MODEL=$(printf '%q' "$MODEL_KEY") \
ORDERING_MODEL=$(printf '%q' "$MODEL_KEY") \
EXECUTOR_MODEL=$(printf '%q' "$MODEL_KEY") \
DECISION_MODE=$(printf '%q' "$DECISION_MODE") \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
PAUSE_HHMM_WINDOWS=$(printf '%q' "$PAUSE_HHMM_WINDOWS") \
PAUSE_TIMEZONE=$(printf '%q' "$PAUSE_TIMEZONE") \
bash $(printf '%q' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"

echo "=================================================="
echo " DeepSeek-V4-flash OLD-6 macro (nothink)"
echo " Tmux     : ${SESSION}"
echo " Batch    : game_records/${BATCH_NAME}/"
echo " Models   : ${MODEL_KEY} x3"
echo " Jobs     : 270 (no veryhard)"
echo " Concur   : ${CONCURRENCY}"
echo " Pause    : ${PAUSE_HHMM_WINDOWS} (${PAUSE_TIMEZONE})"
echo " Attach   : tmux attach -t ${SESSION}"
echo " Logs     : game_records/${BATCH_NAME}_stdout.log"
echo "=================================================="
