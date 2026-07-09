#!/usr/bin/env bash
# 6 strategies vs 3 races @ KairosJunctionLE (default map)
# naming/ordering: Qwen3-32b_think (thinking)
# executor: Qwen3-32b (no thinking)
# difficulties: easy, medium, mediumhard | 3 repeats per combo
#
# Usage:
#   bash tools/start_qwen32b_think_nothink_exec_v7_sweep.sh
#
# Resume:
#   START_INDEX=42 bash tools/start_qwen32b_think_nothink_exec_v7_sweep.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

SESSION="${TMUX_SESSION:-qwen32b_think_nothink_exec_v7_sweep}"
BATCH_NAME="${BATCH_NAME:-qwen32b_think_nothink_exec_v7_r3}"
CONCURRENCY="${CONCURRENCY:-20}"
REPEATS="${REPEATS:-3}"
STRATEGIES="${STRATEGIES:-bio,safe_tvt_raven,three_rax_stim,two_base_tanks,tank_thor_mech,battle_cruisers}"
DIFFICULTIES="${DIFFICULTIES:-easy,medium,mediumhard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-random}"
MAPS="${MAPS:-KairosJunctionLE}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
NAMING_MODEL="${NAMING_MODEL:-Qwen3-32b_think}"
ORDERING_MODEL="${ORDERING_MODEL:-Qwen3-32b_think}"
EXECUTOR_MODEL="${EXECUTOR_MODEL:-Qwen3-32b}"
TOTAL_JOBS=162

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Killing existing tmux session: $SESSION"
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  sleep 1
fi

pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${BATCH_NAME}" 2>/dev/null || true
pkill -f "run_experiment.py.*--batch-name ${BATCH_NAME}" 2>/dev/null || true
sleep 1

tmux new-session -d -s "$SESSION" -n sweep \
  "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$BATCH_NAME") \
CONCURRENCY=$(printf '%q' "$CONCURRENCY") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
NAMING_MODEL=$(printf '%q' "$NAMING_MODEL") \
ORDERING_MODEL=$(printf '%q' "$ORDERING_MODEL") \
EXECUTOR_MODEL=$(printf '%q' "$EXECUTOR_MODEL") \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
bash $(printf \'%q\' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"
echo "=================================================="
echo " Tmux session      : $SESSION"
echo " Batch folder      : game_records/${BATCH_NAME}/"
echo " Map               : ${MAPS}"
echo " Naming/Ordering   : ${NAMING_MODEL} (thinking)"
echo " Executor          : ${EXECUTOR_MODEL} (no thinking)"
echo " Strategies        : ${STRATEGIES}"
echo " Opponent          : ${ENEMY_RACES} | build=${ENEMY_BUILD}"
echo " Difficulties      : ${DIFFICULTIES}"
echo " Repeats           : ${REPEATS} per combo"
echo " Concurrency       : ${CONCURRENCY}"
echo " Total jobs        : ${TOTAL_JOBS}"
echo " Attach            : tmux attach -t $SESSION"
echo " Logs              : game_records/${BATCH_NAME}_stdout.log"
echo "=================================================="
