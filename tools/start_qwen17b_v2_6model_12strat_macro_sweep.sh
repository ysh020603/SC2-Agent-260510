#!/usr/bin/env bash
# 12 Terran strategies (6 old + 6 new) vs 3 races (macro) @ KairosJunctionLE
# 6x Qwen3-1.7b-v2 mix models on 172.18.30.73:8300-8305 (thinking / content_think_tags)
# All modules (naming/ordering/executor) use the same model key per endpoint.
# Matrix: difficulties=veryeasy,medium,hard,veryhard; repeats=5 -> 720 jobs/model
#
# Usage:
#   bash tools/start_qwen17b_v2_6model_12strat_macro_sweep.sh            # all 6
#   bash tools/start_qwen17b_v2_6model_12strat_macro_sweep.sh balanced_two_stage
# Resume:
#   CONCURRENCY=8 SKIP_COMPLETED=1 bash tools/start_qwen17b_v2_6model_12strat_macro_sweep.sh

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
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard,veryhard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
CONCURRENCY="${CONCURRENCY:-8}"
DECISION_MODE="${DECISION_MODE:-three-stage}"
AUTO_EXIT="${AUTO_EXIT:-1}"
TOTAL_JOBS=720

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
  pkill -f "run_experiment.py.*--batch-name ${batch}" 2>/dev/null || true
  sleep 1

  tmux new-session -d -s "$session" -n sweep \
    "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$batch") \
CONCURRENCY=$(printf '%q' "$CONCURRENCY") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
SKIP_COMPLETED=$(printf '%q' "${SKIP_COMPLETED:-0}") \
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
  echo " Mode    : ${DECISION_MODE} | thinking on"
  echo " Diffs   : ${DIFFICULTIES}"
  echo " Jobs    : ${TOTAL_JOBS}"
  echo " Concur  : ${CONCURRENCY}"
  echo " Attach  : tmux attach -t ${session}"
  echo " Logs    : game_records/${batch}_stdout.log"
  echo "--------------------------------------------------"
}

declare -A MODEL_KEY=(
  [balanced_two_stage]="Qwen3-1.7b-v2-our-balanced-two-stage_think"
  [balanced_cot_only]="Qwen3-1.7b-v2-our-balanced-cot-only_think"
  [uniform_two_stage]="Qwen3-1.7b-v2-strategy-uniform-two-stage_think"
  [uniform_cot_only]="Qwen3-1.7b-v2-strategy-uniform-cot-only_think"
  [random_two_stage]="Qwen3-1.7b-v2-random-instance-two-stage_think"
  [random_cot_only]="Qwen3-1.7b-v2-random-instance-cot-only_think"
)

declare -A BATCH_NAME=(
  [balanced_two_stage]="qwen17b_v2_balanced_two_stage_12strat_macro_r5"
  [balanced_cot_only]="qwen17b_v2_balanced_cot_only_12strat_macro_r5"
  [uniform_two_stage]="qwen17b_v2_uniform_two_stage_12strat_macro_r5"
  [uniform_cot_only]="qwen17b_v2_uniform_cot_only_12strat_macro_r5"
  [random_two_stage]="qwen17b_v2_random_two_stage_12strat_macro_r5"
  [random_cot_only]="qwen17b_v2_random_cot_only_12strat_macro_r5"
)

declare -A SESSION_NAME=(
  [balanced_two_stage]="qwen17b_v2_balanced_two_stage_12strat_macro_sweep"
  [balanced_cot_only]="qwen17b_v2_balanced_cot_only_12strat_macro_sweep"
  [uniform_two_stage]="qwen17b_v2_uniform_two_stage_12strat_macro_sweep"
  [uniform_cot_only]="qwen17b_v2_uniform_cot_only_12strat_macro_sweep"
  [random_two_stage]="qwen17b_v2_random_two_stage_12strat_macro_sweep"
  [random_cot_only]="qwen17b_v2_random_cot_only_12strat_macro_sweep"
)

ALL_TAGS=(balanced_two_stage balanced_cot_only uniform_two_stage uniform_cot_only random_two_stage random_cot_only)

TARGET="${1:-all}"
TAGS=()
case "$TARGET" in
  all)
    TAGS=("${ALL_TAGS[@]}")
    ;;
  balanced_two_stage|balanced_cot_only|uniform_two_stage|uniform_cot_only|random_two_stage|random_cot_only)
    TAGS=("$TARGET")
    ;;
  *)
    echo "Usage: $0 {all|balanced_two_stage|balanced_cot_only|uniform_two_stage|uniform_cot_only|random_two_stage|random_cot_only}" >&2
    exit 1
    ;;
esac

echo "=================================================="
echo " Qwen3-1.7b-v2 6-model macro sweep"
echo " Map/build : KairosJunctionLE / macro"
echo " Diffs     : ${DIFFICULTIES}"
echo " Concur/EP : ${CONCURRENCY}  (x${#TAGS[@]} endpoints)"
echo "=================================================="

for tag in "${TAGS[@]}"; do
  _start_one "$tag" "${MODEL_KEY[$tag]}" "${BATCH_NAME[$tag]}" "${SESSION_NAME[$tag]}"
  echo ""
done
