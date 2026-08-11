#!/usr/bin/env bash
# OLD-6 macro sweeps for two local Qwen3-1.7B nocot (non-thinking) models:
#   - stage1 (pre-train):  :8010  Qwen3-1.7b-our-balanced-nocot-stage1
#   - mix-grpo-v2 (post):   :8011  Qwen3-1.7b-our-balanced-nocot-mix-grpo-v2-nothink
#
# Protocol: OLD-6, P/T/Z, macro, KairosJunctionLE,
#           difficulties=veryeasy,medium,hard (NO veryhard), repeats=5
#           -> 6 * 3 * 3 * 5 = 270 jobs / group
# Concurrency: 20 each. Thinking OFF (is_reasoning=false in API config).
#
# Usage:
#   bash tools/start_old6_balanced_nocot_pair_macro.sh
#   bash tools/start_old6_balanced_nocot_pair_macro.sh stage1
#   bash tools/start_old6_balanced_nocot_pair_macro.sh mix_grpo_v2
# Resume:
#   SKIP_COMPLETED=1 bash tools/start_old6_balanced_nocot_pair_macro.sh

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
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
CONCURRENCY="${CONCURRENCY:-20}"
DECISION_MODE="${DECISION_MODE:-three-stage}"
AUTO_EXIT="${AUTO_EXIT:-1}"
SKIP_COMPLETED="${SKIP_COMPLETED:-0}"
SCHEDULE_BALANCE="${SCHEDULE_BALANCE:-}"
TOTAL_JOBS=270

_start_one() {
  local tag="$1"
  local model_key="$2"
  local batch="$3"
  local session="$4"

  if tmux has-session -t "$session" 2>/dev/null; then
    echo "Killing existing tmux session: $session"
    tmux kill-session -t "$session" 2>/dev/null || true
    sleep 1
  fi
  pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${batch}" 2>/dev/null || true
  pkill -f "run_experiment.py --batch-name ${batch} " 2>/dev/null || true
  sleep 1

  tmux new-session -d -s "$session" -n sweep \
    "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$batch") \
CONCURRENCY=$(printf '%q' "$CONCURRENCY") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=0 \
SKIP_COMPLETED=$(printf '%q' "$SKIP_COMPLETED") \
AUTO_EXIT=$(printf '%q' "$AUTO_EXIT") \
MAX_ATTEMPTS=$(printf '%q' "${MAX_ATTEMPTS:-3}") \
NAMING_MODEL=$(printf '%q' "$model_key") \
ORDERING_MODEL=$(printf '%q' "$model_key") \
EXECUTOR_MODEL=$(printf '%q' "$model_key") \
DECISION_MODE=$(printf '%q' "$DECISION_MODE") \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
SCHEDULE_BALANCE=$(printf '%q' "$SCHEDULE_BALANCE") \
bash $(printf '%q' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"

  echo "--------------------------------------------------"
  echo " Started : ${tag}"
  echo " Tmux    : ${session}"
  echo " Batch   : game_records/${batch}/"
  echo " Model   : ${model_key} x3 (naming=ordering=executor, nothink)"
  echo " Jobs    : ${TOTAL_JOBS} (no veryhard)"
  echo " Concur  : ${CONCURRENCY}"
  echo " Skip    : ${SKIP_COMPLETED}"
  echo " Attach  : tmux attach -t ${session}"
  echo " Logs    : game_records/${batch}_stdout.log"
  echo "--------------------------------------------------"
}

TARGET="${1:-all}"

case "$TARGET" in
  all|stage1|mix_grpo_v2) ;;
  *)
    echo "Usage: $0 {all|stage1|mix_grpo_v2}" >&2
    exit 1
    ;;
esac

echo "=================================================="
echo " OLD-6 balanced nocot pair (thinking OFF)"
echo " Concur    : ${CONCURRENCY}"
echo " Jobs/group: ${TOTAL_JOBS}"
echo " Target    : ${TARGET}"
echo "=================================================="

if [[ "$TARGET" == "all" || "$TARGET" == "stage1" ]]; then
  _start_one \
    "stage1_pretrain" \
    "Qwen3-1.7b-our-balanced-nocot-stage1" \
    "qwen17b_balanced_nocot_stage1_6old_macro_r5" \
    "old6_qwen17b_nocot_stage1"
  echo ""
fi

if [[ "$TARGET" == "all" || "$TARGET" == "mix_grpo_v2" ]]; then
  _start_one \
    "mix_grpo_v2_posttrain" \
    "Qwen3-1.7b-our-balanced-nocot-mix-grpo-v2-nothink" \
    "qwen17b_balanced_nocot_mix_grpo_v2_6old_macro_r5" \
    "old6_qwen17b_nocot_mix_grpo_v2"
  echo ""
fi
