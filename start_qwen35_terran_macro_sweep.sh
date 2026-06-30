#!/usr/bin/env bash
# Qwen35-27b (no thinking) x 6 strategies vs Terran Macro @ KairosJunctionLE
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
SESSION="${TMUX_SESSION:-qwen35_terran_macro_sweep}"
BATCH_NAME="${BATCH_NAME:-qwen35_terran_macro_v6}"
MODEL="${MODEL:-Qwen35-27b}"

if ! command -v tmux >/dev/null 2>&1; then echo "tmux not found." >&2; exit 1; fi
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Tmux session already exists: $SESSION"; echo "Attach: tmux attach -t $SESSION"; exit 1
fi
pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${BATCH_NAME}" 2>/dev/null || true
pkill -f "run_experiment.py.*--batch-name ${BATCH_NAME}" 2>/dev/null || true
sleep 2

tmux new-session -d -s "$SESSION" -n sweep \
  "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$BATCH_NAME") \
CONCURRENCY=$(printf '%q' "${CONCURRENCY:-6}") \
REPEATS=$(printf '%q' "${REPEATS:-3}") \
GAME_TIME_LIMIT=$(printf '%q' "${GAME_TIME_LIMIT:-1200}") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
NAMING_MODEL=$(printf '%q' "$MODEL") \
ORDERING_MODEL=$(printf '%q' "$MODEL") \
EXECUTOR_MODEL=$(printf '%q' "$MODEL") \
STRATEGIES=$(printf '%q' "${STRATEGIES:-bio,safe_tvt_raven,three_rax_stim,two_base_tanks,tank_thor_mech,battle_cruisers}") \
DIFFICULTIES=$(printf '%q' "${DIFFICULTIES:-veryeasy,easy,medium,mediumhard,hard}") \
ENEMY_RACES=terran ENEMY_BUILD=macro MAPS=KairosJunctionLE \
bash tools/run_strategy_sweep_tmux.sh"

echo "=================================================="
echo " Tmux session : $SESSION"
echo " Batch        : game_records/${BATCH_NAME}/"
echo " Models       : ${MODEL} (naming/ordering/executor)"
echo " Concurrency  : ${CONCURRENCY:-6} | Jobs: 90"
echo " Attach       : tmux attach -t $SESSION"
echo "=================================================="
