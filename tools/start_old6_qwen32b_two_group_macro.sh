#!/usr/bin/env bash
# OLD-6 macro sweeps for Qwen3-32B (no veryhard).
#
# Group A (all_think): naming=ordering=executor=Qwen3-32b_think, concurrency=15
# Group B (kimi_order_exec32b): naming=ordering=Kimi-k2.5_think, executor=Qwen3-32b_think, concurrency=13
# Group C (all_nothink): naming=ordering=executor=Qwen3-32b, concurrency=10
#
# Protocol: OLD-6 strategies, P/T/Z, macro, KairosJunctionLE,
#           difficulties=veryeasy,medium,hard (NO veryhard), repeats=5
#           -> 6 * 3 * 3 * 5 = 270 jobs / group
#
# Usage:
#   bash tools/start_old6_qwen32b_two_group_macro.sh
#   bash tools/start_old6_qwen32b_two_group_macro.sh all_think
#   bash tools/start_old6_qwen32b_two_group_macro.sh kimi_order
#   bash tools/start_old6_qwen32b_two_group_macro.sh all_nothink
#   # Add +12 workers to running kimi_order (does NOT kill existing sweep):
#   bash tools/start_old6_qwen32b_two_group_macro.sh kimi_order_boost
#   # Reorder remaining by difficulty-first balance (kills main+boost, conc=25):
#   bash tools/start_old6_qwen32b_two_group_macro.sh kimi_order_rebalance
# Resume:
#   SKIP_COMPLETED=1 bash tools/start_old6_qwen32b_two_group_macro.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

OLD_STRATEGIES="banshees,battle_cruisers,bio,cyclones,marine_rush,two_base_tanks"
STRATEGIES="${STRATEGIES:-${OLD_STRATEGIES}}"
# Fresh batches: no VH in the list (270 jobs, indices 0..269).
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard}"
EXCLUDE_DIFFICULTIES="${EXCLUDE_DIFFICULTIES:-}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
DECISION_MODE="${DECISION_MODE:-three-stage}"
AUTO_EXIT="${AUTO_EXIT:-1}"
SKIP_COMPLETED="${SKIP_COMPLETED:-0}"
SCHEDULE_BALANCE="${SCHEDULE_BALANCE:-}"
TOTAL_JOBS=270

QWEN_KEY="${QWEN_KEY:-Qwen3-32b_think}"
QWEN_NOTHINK_KEY="${QWEN_NOTHINK_KEY:-Qwen3-32b}"
KIMI_KEY="${KIMI_KEY:-Kimi-k2.5_think}"

CONC_ALL="${CONC_ALL:-${CONCURRENCY_ALL:-15}}"
CONC_KIMI="${CONC_KIMI:-${CONCURRENCY_KIMI:-13}}"
CONC_KIMI_BOOST="${CONC_KIMI_BOOST:-12}"   # 13 + 12 = 25 total with original sweep
CONC_KIMI_MERGED="${CONC_KIMI_MERGED:-25}" # single-process restart (difficulty-balanced)
CONC_NOTHINK="${CONC_NOTHINK:-${CONCURRENCY_NOTHINK:-10}}"

_launch_tmux() {
  local tag="$1"
  local batch="$2"
  local session="$3"
  local concurrency="$4"
  local naming="$5"
  local ordering="$6"
  local executor="$7"
  local skip_completed="$8"
  local log_suffix="${9:-}"
  local schedule_balance="${10:-${SCHEDULE_BALANCE}}"

  tmux new-session -d -s "$session" -n sweep \
    "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$batch") \
CONCURRENCY=$(printf '%q' "$concurrency") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=0 \
SKIP_COMPLETED=$(printf '%q' "$skip_completed") \
EXCLUDE_DIFFICULTIES=$(printf '%q' "$EXCLUDE_DIFFICULTIES") \
AUTO_EXIT=$(printf '%q' "$AUTO_EXIT") \
MAX_ATTEMPTS=$(printf '%q' "${MAX_ATTEMPTS:-3}") \
NAMING_MODEL=$(printf '%q' "$naming") \
ORDERING_MODEL=$(printf '%q' "$ordering") \
EXECUTOR_MODEL=$(printf '%q' "$executor") \
DECISION_MODE=$(printf '%q' "$DECISION_MODE") \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
SCHEDULE_BALANCE=$(printf '%q' "$schedule_balance") \
LOG_SUFFIX=$(printf '%q' "$log_suffix") \
bash $(printf '%q' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"

  echo "--------------------------------------------------"
  echo " Started : ${tag}"
  echo " Tmux    : ${session}"
  echo " Batch   : game_records/${batch}/"
  echo " Naming  : ${naming}"
  echo " Ordering: ${ordering}"
  echo " Executor: ${executor}"
  echo " Diffs   : ${DIFFICULTIES}  exclude=${EXCLUDE_DIFFICULTIES:-none}"
  echo " Jobs    : ${TOTAL_JOBS}"
  echo " Concur  : ${concurrency}"
  echo " Balance : ${schedule_balance:-none}"
  echo " Skip    : ${skip_completed}"
  echo " Attach  : tmux attach -t ${session}"
  echo " Logs    : game_records/${batch}${log_suffix}_stdout.log"
  echo "--------------------------------------------------"
}

_start_one() {
  local tag="$1"
  local batch="$2"
  local session="$3"
  local concurrency="$4"
  local naming="$5"
  local ordering="$6"
  local executor="$7"

  if tmux has-session -t "$session" 2>/dev/null; then
    echo "Killing existing tmux session: $session"
    tmux kill-session -t "$session" 2>/dev/null || true
    sleep 1
  fi
  pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${batch}" 2>/dev/null || true
  pkill -f "run_experiment.py --batch-name ${batch} " 2>/dev/null || true
  sleep 1

  _launch_tmux "$tag" "$batch" "$session" "$concurrency" \
    "$naming" "$ordering" "$executor" "$SKIP_COMPLETED" ""
}

# Add workers to an already-running batch without killing it.
# Relies on per-run flock + --skip-completed to avoid double work.
_start_boost() {
  local tag="$1"
  local batch="$2"
  local session="$3"
  local concurrency="$4"
  local naming="$5"
  local ordering="$6"
  local executor="$7"

  if tmux has-session -t "$session" 2>/dev/null; then
    echo "Boost session already exists: $session (leave as-is)"
    return 0
  fi

  _launch_tmux "$tag" "$batch" "$session" "$concurrency" \
    "$naming" "$ordering" "$executor" "1" "_boost"
}

TARGET="${1:-all}"

echo "=================================================="
echo " Qwen3-32B OLD-6 macro (no veryhard)"
echo " Qwen think   : ${QWEN_KEY}"
echo " Qwen nothink : ${QWEN_NOTHINK_KEY}"
echo " Kimi key     : ${KIMI_KEY}"
echo "=================================================="

case "$TARGET" in
  all|all_think|kimi_order|both|all_nothink|kimi_order_boost|kimi_order_rebalance) ;;
  *)
    echo "Usage: $0 {all|all_think|kimi_order|all_nothink|kimi_order_boost|kimi_order_rebalance}" >&2
    exit 1
    ;;
esac

if [[ "$TARGET" == "all" || "$TARGET" == "both" || "$TARGET" == "all_think" ]]; then
  _start_one \
    "all_think" \
    "qwen32b_all_think_6old_macro_r5" \
    "old6_qwen32b_all_think" \
    "$CONC_ALL" \
    "$QWEN_KEY" "$QWEN_KEY" "$QWEN_KEY"
  echo ""
fi

if [[ "$TARGET" == "all" || "$TARGET" == "both" || "$TARGET" == "kimi_order" ]]; then
  _start_one \
    "kimi_order" \
    "qwen32b_kimi_order_exec32b_6old_macro_r5" \
    "old6_qwen32b_kimi_order" \
    "$CONC_KIMI" \
    "$KIMI_KEY" "$KIMI_KEY" "$QWEN_KEY"
  echo ""
fi

if [[ "$TARGET" == "kimi_order_boost" ]]; then
  _start_boost \
    "kimi_order_boost(+${CONC_KIMI_BOOST} -> total≈$((CONC_KIMI + CONC_KIMI_BOOST)))" \
    "qwen32b_kimi_order_exec32b_6old_macro_r5" \
    "old6_qwen32b_kimi_order_boost" \
    "$CONC_KIMI_BOOST" \
    "$KIMI_KEY" "$KIMI_KEY" "$QWEN_KEY"
  echo ""
fi

# Kill main+boost, restart as one process with difficulty-first scheduling.
if [[ "$TARGET" == "kimi_order_rebalance" ]]; then
  BATCH_KIMI="qwen32b_kimi_order_exec32b_6old_macro_r5"
  for s in old6_qwen32b_kimi_order old6_qwen32b_kimi_order_boost; do
    if tmux has-session -t "$s" 2>/dev/null; then
      echo "Killing existing tmux session: $s"
      tmux kill-session -t "$s" 2>/dev/null || true
    fi
  done
  pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${BATCH_KIMI}" 2>/dev/null || true
  pkill -f "run_experiment.py --batch-name ${BATCH_KIMI} " 2>/dev/null || true
  sleep 2
  SCHEDULE_BALANCE="${SCHEDULE_BALANCE:-difficulty,race}"
  _launch_tmux \
    "kimi_order_rebalance(conc=${CONC_KIMI_MERGED}, balance=${SCHEDULE_BALANCE})" \
    "$BATCH_KIMI" \
    "old6_qwen32b_kimi_order" \
    "$CONC_KIMI_MERGED" \
    "$KIMI_KEY" "$KIMI_KEY" "$QWEN_KEY" \
    "1" \
    "_rebalance" \
    "$SCHEDULE_BALANCE"
  echo ""
fi

if [[ "$TARGET" == "all_nothink" || "$TARGET" == "all" ]]; then
  # 'all' historically meant both think groups; keep that. Use explicit all_nothink for C.
  if [[ "$TARGET" == "all_nothink" ]]; then
    _start_one \
      "all_nothink" \
      "qwen32b_all_nothink_6old_macro_r5" \
      "old6_qwen32b_all_nothink" \
      "$CONC_NOTHINK" \
      "$QWEN_NOTHINK_KEY" "$QWEN_NOTHINK_KEY" "$QWEN_NOTHINK_KEY"
    echo ""
  fi
fi
