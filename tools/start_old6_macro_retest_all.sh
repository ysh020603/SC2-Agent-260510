#!/usr/bin/env bash
# Retest OLD-6 Terran strategies only (no NEW strategies) vs 3 races (macro)
# @ KairosJunctionLE, difficulties=veryeasy,medium,hard,veryhard, repeats=5
# -> 6 * 3 * 4 * 5 = 360 jobs per model.
#
# Models (all modules = same key; thinking on for Qwen; Kimi no-thinking):
#   6x qwen3-1.7b-v2-*          :8300-8305
#   mix-grpo-v2-0719-step318    :8306
#   qwen3-1.7b base             :8307
#   kimi_all (Kimi-k2.5)        external
#
# No SwanLab. Runs each target in its own tmux session.
#
# Usage:
#   bash tools/start_old6_macro_retest_all.sh              # all 9
#   bash tools/start_old6_macro_retest_all.sh kimi_all
#   bash tools/start_old6_macro_retest_all.sh mix_grpo_v2
# Resume:
#   SKIP_COMPLETED=1 CONCURRENCY=8 bash tools/start_old6_macro_retest_all.sh

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
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard,veryhard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
CONCURRENCY_QWEN="${CONCURRENCY_QWEN:-${CONCURRENCY:-8}}"
CONCURRENCY_KIMI="${CONCURRENCY_KIMI:-2}"
DECISION_MODE="${DECISION_MODE:-three-stage}"
AUTO_EXIT="${AUTO_EXIT:-1}"
SKIP_COMPLETED="${SKIP_COMPLETED:-0}"
TOTAL_JOBS=360

_start_one() {
  local tag="$1"
  local model_key="$2"
  local batch="$3"
  local session="$4"
  local concurrency="$5"

  if tmux has-session -t "$session" 2>/dev/null; then
    echo "Killing existing tmux session: $session"
    tmux kill-session -t "$session" 2>/dev/null || true
    sleep 1
  fi

  pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${batch}" 2>/dev/null || true
  pkill -f "run_experiment.py.*--batch-name ${batch}" 2>/dev/null || true
  sleep 1

  tmux new-session -d -s "$session" -n sweep \
    "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$batch") \
CONCURRENCY=$(printf '%q' "$concurrency") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
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
bash $(printf '%q' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"

  echo "--------------------------------------------------"
  echo " Started : ${tag}"
  echo " Tmux    : ${session}"
  echo " Batch   : game_records/${batch}/"
  echo " Model   : ${model_key} (naming=ordering=executor)"
  echo " Strat   : OLD-6 only"
  echo " Diffs   : ${DIFFICULTIES}"
  echo " Jobs    : ${TOTAL_JOBS}"
  echo " Concur  : ${concurrency}"
  echo " Attach  : tmux attach -t ${session}"
  echo " Logs    : game_records/${batch}_stdout.log"
  echo "--------------------------------------------------"
}

# tag -> model_key | batch | session | concurrency
declare -A MODEL_KEY=(
  [balanced_two_stage]="Qwen3-1.7b-v2-our-balanced-two-stage_think"
  [balanced_cot_only]="Qwen3-1.7b-v2-our-balanced-cot-only_think"
  [uniform_two_stage]="Qwen3-1.7b-v2-strategy-uniform-two-stage_think"
  [uniform_cot_only]="Qwen3-1.7b-v2-strategy-uniform-cot-only_think"
  [random_two_stage]="Qwen3-1.7b-v2-random-instance-two-stage_think"
  [random_cot_only]="Qwen3-1.7b-v2-random-instance-cot-only_think"
  [mix_grpo_v2]="Qwen3-1.7b-sc2-mix-grpo-v2-0719-step318_think"
  [base_8307]="Qwen3-1.7b-base_8307_think"
  [kimi_all]="Kimi-k2.5"
)

declare -A BATCH_NAME=(
  [balanced_two_stage]="qwen17b_v2_balanced_two_stage_6old_macro_r5"
  [balanced_cot_only]="qwen17b_v2_balanced_cot_only_6old_macro_r5"
  [uniform_two_stage]="qwen17b_v2_uniform_two_stage_6old_macro_r5"
  [uniform_cot_only]="qwen17b_v2_uniform_cot_only_6old_macro_r5"
  [random_two_stage]="qwen17b_v2_random_two_stage_6old_macro_r5"
  [random_cot_only]="qwen17b_v2_random_cot_only_6old_macro_r5"
  [mix_grpo_v2]="qwen17b_mix_grpo_v2_0719_step318_6old_macro_r5"
  [base_8307]="qwen17b_base_8307_6old_macro_r5"
  [kimi_all]="kimi_nothink_6old_macro_r5"
)

declare -A SESSION_NAME=(
  [balanced_two_stage]="old6_balanced_two_stage"
  [balanced_cot_only]="old6_balanced_cot_only"
  [uniform_two_stage]="old6_uniform_two_stage"
  [uniform_cot_only]="old6_uniform_cot_only"
  [random_two_stage]="old6_random_two_stage"
  [random_cot_only]="old6_random_cot_only"
  [mix_grpo_v2]="old6_mix_grpo_v2"
  [base_8307]="old6_base_8307"
  [kimi_all]="old6_kimi_all"
)

ALL_TAGS=(
  balanced_two_stage balanced_cot_only
  uniform_two_stage uniform_cot_only
  random_two_stage random_cot_only
  mix_grpo_v2 base_8307 kimi_all
)

TARGET="${1:-all}"
TAGS=()
case "$TARGET" in
  all) TAGS=("${ALL_TAGS[@]}") ;;
  balanced_two_stage|balanced_cot_only|uniform_two_stage|uniform_cot_only|random_two_stage|random_cot_only|mix_grpo_v2|base_8307|kimi_all)
    TAGS=("$TARGET")
    ;;
  *)
    echo "Usage: $0 {all|balanced_two_stage|balanced_cot_only|uniform_two_stage|uniform_cot_only|random_two_stage|random_cot_only|mix_grpo_v2|base_8307|kimi_all}" >&2
    exit 1
    ;;
esac

echo "=================================================="
echo " OLD-6 macro retest (no NEW strategies, no SwanLab)"
echo " Map/build : KairosJunctionLE / macro"
echo " Diffs     : ${DIFFICULTIES}"
echo " Strategies: ${STRATEGIES}"
echo " Jobs/model: ${TOTAL_JOBS}"
echo " Qwen conc : ${CONCURRENCY_QWEN} | Kimi conc: ${CONCURRENCY_KIMI}"
echo " Targets   : ${#TAGS[@]}"
echo "=================================================="

for tag in "${TAGS[@]}"; do
  conc="$CONCURRENCY_QWEN"
  if [[ "$tag" == "kimi_all" ]]; then
    conc="$CONCURRENCY_KIMI"
  fi
  _start_one "$tag" "${MODEL_KEY[$tag]}" "${BATCH_NAME[$tag]}" "${SESSION_NAME[$tag]}" "$conc"
  echo ""
done
