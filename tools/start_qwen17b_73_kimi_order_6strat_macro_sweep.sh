#!/usr/bin/env bash
# 6 old Terran strategies vs 3 races (macro) @ KairosJunctionLE
# Hybrid: trained naming/executor (*_73) + Kimi-k2.5 ordering (no thinking)
#
# Usage:
#   bash tools/start_qwen17b_73_kimi_order_6strat_macro_sweep.sh
# Resume: CONCURRENCY=4 SKIP_COMPLETED=1 bash tools/start_qwen17b_73_kimi_order_6strat_macro_sweep.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

STRATEGIES="${STRATEGIES:-banshees,battle_cruisers,bio,cyclones,marine_rush,two_base_tanks}"
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
CONCURRENCY="${CONCURRENCY:-4}"
NAMING_MODEL="${NAMING_MODEL:-Qwen3-1.7b-sc2-naming_73}"
ORDERING_MODEL="${ORDERING_MODEL:-Kimi-k2.5}"
EXECUTOR_MODEL="${EXECUTOR_MODEL:-Qwen3-1.7b-sc2-executor_73}"

SESSION="${TMUX_SESSION:-qwen17b_73_kimi_order_6strat_macro_sweep}"
BATCH="${BATCH_NAME:-qwen17b_73_kimi_order_6strat_macro_r5}"
TOTAL_JOBS=270

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Killing existing tmux session: $SESSION"
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  sleep 1
fi

pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${BATCH}" 2>/dev/null || true
pkill -f "run_experiment.py.*--batch-name ${BATCH}" 2>/dev/null || true
sleep 1

tmux new-session -d -s "$SESSION" -n sweep \
  "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$BATCH") \
CONCURRENCY=$(printf '%q' "$CONCURRENCY") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
SKIP_COMPLETED=$(printf '%q' "${SKIP_COMPLETED:-0}") \
NAMING_MODEL=$(printf '%q' "$NAMING_MODEL") \
ORDERING_MODEL=$(printf '%q' "$ORDERING_MODEL") \
EXECUTOR_MODEL=$(printf '%q' "$EXECUTOR_MODEL") \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
bash $(printf '%q' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"

echo "=================================================="
echo " Started : kimi_order hybrid"
echo " Tmux    : $SESSION"
echo " Batch   : game_records/${BATCH}/"
echo " Naming  : ${NAMING_MODEL}"
echo " Order   : ${ORDERING_MODEL} (Kimi no thinking)"
echo " Exec    : ${EXECUTOR_MODEL}"
echo " Map     : KairosJunctionLE | build=macro"
echo " Diffs   : ${DIFFICULTIES}"
echo " Strategies: ${STRATEGIES}"
echo " Jobs    : ${TOTAL_JOBS} (6 strategies x 3 races x 3 diffs x 5 reps)"
echo " Concur  : ${CONCURRENCY}"
echo " Attach  : tmux attach -t ${SESSION}"
echo " Logs    : game_records/${BATCH}_stdout.log"
echo "=================================================="
