#!/usr/bin/env bash
# Supplement kimi_all (kimi_nothink_12strat_macro_r5) with missing veryhard difficulty.
# Keeps the same batch directory; uses --index-base 540 so run indices do not collide
# with the existing 540 veryeasy/medium/hard records.
#
# Concurrency matches the original documented run (CONCURRENCY=2).
#
# Usage:
#   bash tools/start_kimi_nothink_12strat_macro_veryhard_supplement.sh
# Resume:
#   SKIP_COMPLETED=1 bash tools/start_kimi_nothink_12strat_macro_veryhard_supplement.sh

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
DIFFICULTIES="${DIFFICULTIES:-veryhard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
# Match original kimi_all documented concurrency
CONCURRENCY="${CONCURRENCY:-2}"
INDEX_BASE="${INDEX_BASE:-540}"
NAMING_MODEL="${NAMING_MODEL:-Kimi-k2.5}"
ORDERING_MODEL="${ORDERING_MODEL:-Kimi-k2.5}"
EXECUTOR_MODEL="${EXECUTOR_MODEL:-Kimi-k2.5}"
DECISION_MODE="${DECISION_MODE:-three-stage}"
AUTO_EXIT="${AUTO_EXIT:-1}"
SKIP_COMPLETED="${SKIP_COMPLETED:-1}"

SESSION="${TMUX_SESSION:-kimi_nothink_12strat_macro_veryhard_supp}"
BATCH="${BATCH_NAME:-kimi_nothink_12strat_macro_r5}"
LOG_SUFFIX="${LOG_SUFFIX:-_veryhard}"
TOTAL_JOBS=180

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Killing existing tmux session: $SESSION"
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  sleep 1
fi

tmux new-session -d -s "$SESSION" -n sweep \
  "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$BATCH") \
CONCURRENCY=$(printf '%q' "$CONCURRENCY") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
INDEX_BASE=$(printf '%q' "$INDEX_BASE") \
SKIP_COMPLETED=$(printf '%q' "$SKIP_COMPLETED") \
AUTO_EXIT=$(printf '%q' "$AUTO_EXIT") \
MAX_ATTEMPTS=$(printf '%q' "${MAX_ATTEMPTS:-3}") \
LOG_SUFFIX=$(printf '%q' "$LOG_SUFFIX") \
NAMING_MODEL=$(printf '%q' "$NAMING_MODEL") \
ORDERING_MODEL=$(printf '%q' "$ORDERING_MODEL") \
EXECUTOR_MODEL=$(printf '%q' "$EXECUTOR_MODEL") \
DECISION_MODE=$(printf '%q' "$DECISION_MODE") \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
bash $(printf '%q' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"

echo "=================================================="
echo " Started : kimi_all veryhard supplement"
echo " Tmux    : $SESSION"
echo " Batch   : game_records/${BATCH}/  (same as original)"
echo " Models  : ${NAMING_MODEL} (no thinking)"
echo " Diffs   : ${DIFFICULTIES}"
echo " Index   : base=${INDEX_BASE} -> run540..run719"
echo " Jobs    : ${TOTAL_JOBS} (12 strat x 3 races x 1 diff x 5 reps)"
echo " Concur  : ${CONCURRENCY} (matches original kimi_all)"
echo " Attach  : tmux attach -t ${SESSION}"
echo " Logs    : game_records/${BATCH}${LOG_SUFFIX}_stdout.log"
echo "=================================================="
