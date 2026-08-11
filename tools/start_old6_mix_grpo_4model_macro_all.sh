#!/usr/bin/env bash
# OLD-6 macro sweep for 4x sc2-mix-grpo-* models (:8000-:8003 on 172.18.30.162).
# Same protocol as prior OLD-6 retests:
#   strategies=OLD-6, races=P/T/Z, build=macro, map=KairosJunctionLE,
#   difficulties=veryeasy,medium,hard,veryhard, repeats=5
#   -> 6 * 3 * 4 * 5 = 360 jobs per model
#   three-stage, naming=ordering=executor=same key, thinking on, no SwanLab
#
# Usage:
#   CONCURRENCY=45 bash tools/start_old6_mix_grpo_4model_macro_all.sh
#   bash tools/start_old6_mix_grpo_4model_macro_all.sh cot_only
# Resume:
#   SKIP_COMPLETED=1 CONCURRENCY=45 bash tools/start_old6_mix_grpo_4model_macro_all.sh

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
# Drop VH after indexing so run-index stays compatible with prior 360-job batches.
EXCLUDE_DIFFICULTIES="${EXCLUDE_DIFFICULTIES:-veryhard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
CONCURRENCY="${CONCURRENCY:-45}"
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
EXCLUDE_DIFFICULTIES=$(printf '%q' "$EXCLUDE_DIFFICULTIES") \
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
  echo " Exclude : ${EXCLUDE_DIFFICULTIES:-'(none)'}"
  echo " Jobs    : ${TOTAL_JOBS}"
  echo " Concur  : ${concurrency}"
  echo " Attach  : tmux attach -t ${session}"
  echo " Logs    : game_records/${batch}_stdout.log"
  echo "--------------------------------------------------"
}

declare -A MODEL_KEY=(
  [cot_only]="sc2-mix-grpo-cot-only_think"
  [cot_only_resp2048]="sc2-mix-grpo-cot-only-resp2048_think"
  [two_stage]="sc2-mix-grpo-two-stage_think"
  [two_stage_resp2048]="sc2-mix-grpo-two-stage-resp2048_think"
)

declare -A BATCH_NAME=(
  [cot_only]="mix_grpo_cot_only_6old_macro_r5"
  [cot_only_resp2048]="mix_grpo_cot_only_resp2048_6old_macro_r5"
  [two_stage]="mix_grpo_two_stage_6old_macro_r5"
  [two_stage_resp2048]="mix_grpo_two_stage_resp2048_6old_macro_r5"
)

declare -A SESSION_NAME=(
  [cot_only]="old6_mix_cot_only"
  [cot_only_resp2048]="old6_mix_cot_only_r2048"
  [two_stage]="old6_mix_two_stage"
  [two_stage_resp2048]="old6_mix_two_stage_r2048"
)

ALL_TAGS=(cot_only cot_only_resp2048 two_stage two_stage_resp2048)

TARGET="${1:-all}"
TAGS=()
case "$TARGET" in
  all) TAGS=("${ALL_TAGS[@]}") ;;
  cot_only|cot_only_resp2048|two_stage|two_stage_resp2048)
    TAGS=("$TARGET")
    ;;
  *)
    echo "Usage: $0 {all|cot_only|cot_only_resp2048|two_stage|two_stage_resp2048}" >&2
    exit 1
    ;;
esac

echo "=================================================="
echo " OLD-6 mix-grpo 4-model macro sweep (no SwanLab)"
echo " Map/build : KairosJunctionLE / macro"
echo " Diffs     : ${DIFFICULTIES}"
echo " Strategies: ${STRATEGIES}"
echo " Jobs/model: ${TOTAL_JOBS}"
echo " Concur    : ${CONCURRENCY}"
echo " Targets   : ${#TAGS[@]}"
echo "=================================================="

for tag in "${TAGS[@]}"; do
  _start_one "$tag" "${MODEL_KEY[$tag]}" "${BATCH_NAME[$tag]}" "${SESSION_NAME[$tag]}" "$CONCURRENCY"
  echo ""
done
