#!/usr/bin/env bash
# 12 Terran strategies (6 old + 6 new) vs 3 races (macro) @ KairosJunctionLE
# All modules: Qwen3-1.7b-sc2-mix-grpo-v1-step200 (thinking / content_think_tags)
# Experiment matrix mirrors kimi_all (kimi_nothink_12strat_macro_r5).
#
# Usage:
#   bash tools/start_qwen17b_mix_grpo_v1_12strat_macro_sweep.sh
# Resume: CONCURRENCY=15 SKIP_COMPLETED=1 bash tools/start_qwen17b_mix_grpo_v1_12strat_macro_sweep.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

OLD_STRATEGIES="banshees,battle_cruisers,bio,cyclones,marine_rush,two_base_tanks"
NEW_STRATEGIES="raven_screams,yamato_rust_fleet,rusty_bio_mines,blueflame_locks,stim_rush_relay,two_base_matrix_tanks"
STRATEGIES="${STRATEGIES:-${OLD_STRATEGIES},${NEW_STRATEGIES}}"
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
CONCURRENCY="${CONCURRENCY:-15}"
# Thinking-mode pool key (content_think_tags / enable_thinking=true), same template as Qwen3-1.7b_think
MODEL_KEY="${MODEL_KEY:-Qwen3-1.7b-sc2-mix-grpo-v1-step200_think}"
NAMING_MODEL="${NAMING_MODEL:-${MODEL_KEY}}"
ORDERING_MODEL="${ORDERING_MODEL:-${MODEL_KEY}}"
EXECUTOR_MODEL="${EXECUTOR_MODEL:-${MODEL_KEY}}"

SESSION="${TMUX_SESSION:-qwen17b_mix_grpo_v1_12strat_macro_sweep}"
BATCH="${BATCH_NAME:-qwen17b_mix_grpo_v1_12strat_macro_r5}"
TOTAL_JOBS=540

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
echo " Started : mix-grpo-v1-step200 (all modules, thinking)"
echo " Tmux    : $SESSION"
echo " Batch   : game_records/${BATCH}/"
echo " Naming  : ${NAMING_MODEL}"
echo " Order   : ${ORDERING_MODEL}"
echo " Exec    : ${EXECUTOR_MODEL}"
echo " Map     : KairosJunctionLE | build=macro"
echo " Diffs   : ${DIFFICULTIES}"
echo " Strategies: ${STRATEGIES}"
echo " Jobs    : ${TOTAL_JOBS} (12 strategies x 3 races x 3 diffs x 5 reps)"
echo " Concur  : ${CONCURRENCY}"
echo " Attach  : tmux attach -t ${SESSION}"
echo " Logs    : game_records/${BATCH}_stdout.log"
echo "=================================================="
