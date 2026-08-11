#!/usr/bin/env bash
# OLD-6 macro sweeps for 5 local Qwen3-1.7B models on 172.18.30.122:8020-8024.
#
# Groups:
#   base_raw              :8020  nothink
#   base_nothink_grpo     :8021  nothink
#   base_thinking_grpo    :8022  thinking
#   strategy_uniform_grpo :8023  thinking
#   random_instance_grpo  :8024  thinking
#
# Protocol: OLD-6, P/T/Z, macro, KairosJunctionLE,
#           difficulties=veryeasy,medium,hard (NO veryhard), repeats=5
#           -> 6 * 3 * 3 * 5 = 270 jobs / group
# Concurrency: 6 each.
#
# Usage:
#   bash tools/start_old6_five_model_grpo_macro.sh
#   bash tools/start_old6_five_model_grpo_macro.sh base_raw
#   CONCURRENCY=15 bash tools/start_old6_five_model_grpo_macro.sh
# Resume:
#   SKIP_COMPLETED=1 bash tools/start_old6_five_model_grpo_macro.sh

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
CONCURRENCY="${CONCURRENCY:-6}"
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
  echo " Model   : ${model_key} x3 (naming=ordering=executor)"
  echo " Jobs    : ${TOTAL_JOBS} (no veryhard)"
  echo " Concur  : ${CONCURRENCY}"
  echo " Skip    : ${SKIP_COMPLETED}"
  echo " Attach  : tmux attach -t ${session}"
  echo " Logs    : game_records/${batch}_stdout.log"
  echo "--------------------------------------------------"
}

declare -A MODEL_KEY=(
  [base_raw]="Qwen3-1.7b-base-raw"
  [base_nothink_grpo]="Qwen3-1.7b-base-raw-nothink-grpo"
  [base_thinking_grpo]="Qwen3-1.7b-base-raw-thinking-grpo_think"
  [strategy_uniform_grpo]="Qwen3-1.7b-strategy-uniform-cot-only-grpo_think"
  [random_instance_grpo]="Qwen3-1.7b-random-instance-cot-only-grpo_think"
)

declare -A BATCH_NAME=(
  [base_raw]="qwen17b_base_raw_6old_macro_r5"
  [base_nothink_grpo]="qwen17b_base_raw_nothink_grpo_6old_macro_r5"
  [base_thinking_grpo]="qwen17b_base_raw_thinking_grpo_6old_macro_r5"
  [strategy_uniform_grpo]="qwen17b_strategy_uniform_cot_grpo_6old_macro_r5"
  [random_instance_grpo]="qwen17b_random_instance_cot_grpo_6old_macro_r5"
)

declare -A SESSION_NAME=(
  [base_raw]="old6_qwen17b_base_raw"
  [base_nothink_grpo]="old6_qwen17b_base_nothink_grpo"
  [base_thinking_grpo]="old6_qwen17b_base_thinking_grpo"
  [strategy_uniform_grpo]="old6_qwen17b_strategy_uniform_grpo"
  [random_instance_grpo]="old6_qwen17b_random_instance_grpo"
)

declare -A MODE_LABEL=(
  [base_raw]="nothink"
  [base_nothink_grpo]="nothink"
  [base_thinking_grpo]="thinking"
  [strategy_uniform_grpo]="thinking"
  [random_instance_grpo]="thinking"
)

ALL_TAGS=(base_raw base_nothink_grpo base_thinking_grpo strategy_uniform_grpo random_instance_grpo)

TARGET="${1:-all}"
TAGS=()
case "$TARGET" in
  all) TAGS=("${ALL_TAGS[@]}") ;;
  base_raw|base_nothink_grpo|base_thinking_grpo|strategy_uniform_grpo|random_instance_grpo)
    TAGS=("$TARGET")
    ;;
  *)
    echo "Usage: $0 {all|base_raw|base_nothink_grpo|base_thinking_grpo|strategy_uniform_grpo|random_instance_grpo}" >&2
    exit 1
    ;;
esac

echo "=================================================="
echo " OLD-6 five-model GRPO macro (no VH)"
echo " Host      : 172.18.30.122 :8020-:8024"
echo " Concur    : ${CONCURRENCY} / group"
echo " Jobs/group: ${TOTAL_JOBS}"
echo " Targets   : ${TAGS[*]}"
echo "=================================================="

for tag in "${TAGS[@]}"; do
  echo " mode=${MODE_LABEL[$tag]}"
  _start_one \
    "$tag" \
    "${MODEL_KEY[$tag]}" \
    "${BATCH_NAME[$tag]}" \
    "${SESSION_NAME[$tag]}"
  echo ""
done
