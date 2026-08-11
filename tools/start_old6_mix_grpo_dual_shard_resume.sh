#!/usr/bin/env bash
# Resume unfinished mix-grpo cot_only / two_stage with dual API replicas.
#
# Same batch names as before; shard by job index:
#   shard0 -> even indices  -> primary API  (:8000 / :8002)
#   shard1 -> odd  indices  -> replica API  (:8001 / :8003)
# SKIP_COMPLETED=1 + per-run locks avoid double work.
#
# Usage:
#   CONCURRENCY=25 bash tools/start_old6_mix_grpo_dual_shard_resume.sh
#   CONCURRENCY=25 bash tools/start_old6_mix_grpo_dual_shard_resume.sh cot_only
#   CONCURRENCY=25 bash tools/start_old6_mix_grpo_dual_shard_resume.sh two_stage

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
# Keep full difficulty list for stable run-index; drop VH via EXCLUDE_DIFFICULTIES.
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard,veryhard}"
EXCLUDE_DIFFICULTIES="${EXCLUDE_DIFFICULTIES:-veryhard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
CONCURRENCY="${CONCURRENCY:-25}"
DECISION_MODE="${DECISION_MODE:-three-stage}"
AUTO_EXIT="${AUTO_EXIT:-1}"
SKIP_COMPLETED="${SKIP_COMPLETED:-1}"
JOB_STRIDE=2

_start_shard() {
  local tag="$1"          # cot_only | two_stage
  local shard="$2"        # 0 | 1
  local model_key="$3"
  local batch="$4"
  local session="$5"

  if tmux has-session -t "$session" 2>/dev/null; then
    echo "Killing existing tmux session: $session"
    tmux kill-session -t "$session" 2>/dev/null || true
    sleep 1
  fi

  # Only kill this shard's sweep pattern (batch + stride/offset via env in command line is hard);
  # kill by session already stops the sweep. Avoid pkill on whole batch name which would
  # kill the sibling shard — so we do NOT pkill by batch here.

  tmux new-session -d -s "$session" -n sweep \
    "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$batch") \
CONCURRENCY=$(printf '%q' "$CONCURRENCY") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=0 \
JOB_STRIDE=$(printf '%q' "$JOB_STRIDE") \
JOB_OFFSET=$(printf '%q' "$shard") \
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
LOG_SUFFIX=$(printf '%q' "_s${shard}") \
bash $(printf '%q' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"

  echo "--------------------------------------------------"
  echo " Started : ${tag} shard${shard}"
  echo " Tmux    : ${session}"
  echo " Batch   : game_records/${batch}/  (shared)"
  echo " Model   : ${model_key}"
  echo " Shard   : index % ${JOB_STRIDE} == ${shard}"
  echo " Concur  : ${CONCURRENCY}"
  echo " Skip    : ${SKIP_COMPLETED}"
  echo " Exclude : ${EXCLUDE_DIFFICULTIES:-'(none)'}"
  echo " Attach  : tmux attach -t ${session}"
  echo " Logs    : game_records/${batch}_s${shard}_stdout.log"
  echo "--------------------------------------------------"
}

# tag -> batch / primary key / replica key
declare -A BATCH_NAME=(
  [cot_only]="mix_grpo_cot_only_6old_macro_r5"
  [two_stage]="mix_grpo_two_stage_6old_macro_r5"
)
declare -A MODEL_PRIMARY=(
  [cot_only]="sc2-mix-grpo-cot-only_think"
  [two_stage]="sc2-mix-grpo-two-stage_think"
)
declare -A MODEL_REPLICA=(
  [cot_only]="sc2-mix-grpo-cot-only_think_r1"
  [two_stage]="sc2-mix-grpo-two-stage_think_r1"
)

TARGET="${1:-all}"
TAGS=()
case "$TARGET" in
  all) TAGS=(cot_only two_stage) ;;
  cot_only|two_stage) TAGS=("$TARGET") ;;
  *)
    echo "Usage: $0 {all|cot_only|two_stage}" >&2
    exit 1
    ;;
esac

echo "=================================================="
echo " Dual-shard resume for unfinished mix-grpo OLD-6"
echo " Concurrency/shard : ${CONCURRENCY}  (x2 shards/model)"
echo " Stride            : ${JOB_STRIDE}"
echo " Exclude diffs     : ${EXCLUDE_DIFFICULTIES:-'(none)'}"
echo " Targets           : ${TAGS[*]}"
echo "=================================================="

# Stop old single-worker sessions that would fight the new shards.
for tag in "${TAGS[@]}"; do
  for s in "old6_mix_${tag}" "old6_mix_${tag}_s0" "old6_mix_${tag}_s1"; do
    if tmux has-session -t "$s" 2>/dev/null; then
      echo "Stopping old session: $s"
      tmux kill-session -t "$s" 2>/dev/null || true
    fi
  done
  # Stop leftover sweep + in-flight games so per-run flock locks are released.
  pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${BATCH_NAME[$tag]}" 2>/dev/null || true
  pkill -f "run_experiment.py --batch-name ${BATCH_NAME[$tag]} " 2>/dev/null || true
done
sleep 3

for tag in "${TAGS[@]}"; do
  batch="${BATCH_NAME[$tag]}"
  _start_shard "$tag" 0 "${MODEL_PRIMARY[$tag]}" "$batch" "old6_mix_${tag}_s0"
  echo ""
  _start_shard "$tag" 1 "${MODEL_REPLICA[$tag]}" "$batch" "old6_mix_${tag}_s1"
  echo ""
done
