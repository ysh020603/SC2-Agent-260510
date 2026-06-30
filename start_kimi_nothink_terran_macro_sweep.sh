#!/usr/bin/env bash
# Kimi-k2.5 (no thinking) x 6 strategies vs Terran Macro @ KairosJunctionLE
# 5 difficulties x 3 repeats, concurrency=3, tmux
#
# Usage:
#   bash start_kimi_nothink_terran_macro_sweep.sh
# Attach:
#   tmux attach -t kimi_nothink_terran_macro_sweep

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

SESSION="${TMUX_SESSION:-kimi_nothink_terran_macro_sweep}"
BATCH_NAME="${BATCH_NAME:-kimi_nothink_terran_macro_v6}"

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
CONCURRENCY=$(printf '%q' "${CONCURRENCY:-3}") \
REPEATS=$(printf '%q' "${REPEATS:-3}") \
GAME_TIME_LIMIT=$(printf '%q' "${GAME_TIME_LIMIT:-1200}") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
NAMING_MODEL=$(printf '%q' "${NAMING_MODEL:-Kimi-k2.5}") \
ORDERING_MODEL=$(printf '%q' "${ORDERING_MODEL:-Kimi-k2.5}") \
EXECUTOR_MODEL=$(printf '%q' "${EXECUTOR_MODEL:-Kimi-k2.5}") \
STRATEGIES=$(printf '%q' "${STRATEGIES:-bio,safe_tvt_raven,three_rax_stim,two_base_tanks,tank_thor_mech,battle_cruisers}") \
DIFFICULTIES=$(printf '%q' "${DIFFICULTIES:-veryeasy,easy,medium,mediumhard,hard}") \
ENEMY_RACES=terran \
ENEMY_BUILD=macro \
MAPS=KairosJunctionLE \
bash tools/run_strategy_sweep_tmux.sh"

echo "=================================================="
echo " Tmux session      : $SESSION"
echo " Batch folder      : game_records/${BATCH_NAME}/"
echo " Map               : KairosJunctionLE"
echo " Models            : Kimi-k2.5 (naming/ordering/executor, no thinking)"
echo " Strategies        : bio, safe_tvt_raven, three_rax_stim,"
echo "                     two_base_tanks, tank_thor_mech, battle_cruisers"
echo " Opponent          : Terran | build=macro"
echo " Difficulties      : veryeasy, easy, medium, mediumhard, hard"
echo " Repeats           : ${REPEATS:-3} per combo"
echo " Concurrency       : ${CONCURRENCY:-3}"
echo " Total jobs        : 90 (6 x 5 x 3)"
echo " Attach            : tmux attach -t $SESSION"
echo " Stdout/stderr     : game_records/${BATCH_NAME}_stdout.log"
echo "=================================================="
