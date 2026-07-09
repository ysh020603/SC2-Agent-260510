#!/usr/bin/env bash
# BO-list executor sweep: 14 Terran strategies, KairosJunction vs Terran macro.
# Protocol matches game_records/bo_exec_27b_10strat_k_tv_r5 (k_tv_r5).
#
# Usage:
#   bash tools/start_bo_exec_06b_14strat_k_tv_sweep.sh 06b
#   bash tools/start_bo_exec_06b_14strat_k_tv_sweep.sh 06b_think
#   bash tools/start_bo_exec_06b_14strat_k_tv_sweep.sh grpo_5ep
#   bash tools/start_bo_exec_06b_14strat_k_tv_sweep.sh 27b
#   bash tools/start_bo_exec_06b_14strat_k_tv_sweep.sh all
#
# Resume:
#   bash tools/start_bo_exec_06b_14strat_k_tv_sweep.sh 06b

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

source /home/wyq/miniconda3/etc/profile.d/conda.sh
conda activate SC2_0615

VARIANT="${1:-all}"
CONCURRENCY="${CONCURRENCY:-15}"
REPEATS="${REPEATS:-20}"
START_INDEX="${START_INDEX:-0}"
SKIP_COMPLETED="${SKIP_COMPLETED:-1}"
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard}"
ENEMY_RACES="${ENEMY_RACES:-terran}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"

STRATEGIES="${STRATEGIES:-banshees,battle_cruisers,bio,blueflame_locks,cyclones,marine_rush,old_rusty_anvil,raven_screams,rusty,stim_rush_relay,two_base_matrix_tanks,two_base_tanks,yamato_rust_fleet,rusty_bio_mines}"

_common_env() {
  printf '%s\n' \
    "cd $(printf '%q' "$ROOT")" \
    "source /home/wyq/miniconda3/etc/profile.d/conda.sh" \
    "conda activate SC2_0615" \
    "export SC2PATH=\"\${SC2PATH:-/data2/SC2/StarCraftII/}\"" \
    "export PYTHONUTF8=1" \
    "export PYTHONIOENCODING=utf-8" \
    "export CONCURRENCY=$(printf '%q' "$CONCURRENCY")" \
    "export REPEATS=$(printf '%q' "$REPEATS")" \
    "export START_INDEX=$(printf '%q' "$START_INDEX")" \
    "export SKIP_COMPLETED=$(printf '%q' "$SKIP_COMPLETED")" \
    "export DIFFICULTIES=$(printf '%q' "$DIFFICULTIES")" \
    "export ENEMY_RACES=$(printf '%q' "$ENEMY_RACES")" \
    "export ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD")" \
    "export MAPS=$(printf '%q' "$MAPS")" \
    "export GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT")" \
    "export STRATEGIES=$(printf '%q' "$STRATEGIES")"
}

_prepare_batch() {
  local batch="$1"
  local old_batch="$2"
  python tools/prepare_bo_exec_batch.py \
    --batch-name "${batch}" \
    --migrate-from "${old_batch}" \
    --remove-old-batch-dir
}

_launch() {
  local session="$1"
  local batch="$2"
  local old_batch="$3"
  local model="$4"

  _prepare_batch "${batch}" "${old_batch}"

  local inner
  inner="$(_common_env)
export BATCH_NAME=$(printf '%q' "$batch")
export EXECUTOR_MODEL=$(printf '%q' "$model")
bash $(printf \'%q\' "$SCRIPT_DIR/run_bo_exec_sweep_tmux.sh")"
  if tmux has-session -t "$session" 2>/dev/null; then
    echo "[skip] tmux session already exists: $session"
    return 0
  fi

  tmux new-session -d -s "$session" bash -lc "$inner"
  echo "[ok] tmux session: $session | batch=$batch | executor=$model | repeats=$REPEATS"
}

case "$VARIANT" in
  06b)
    _launch bo_exec_06b_14strat_sweep bo_exec_06b_14strat_k_tv_r20 bo_exec_06b_14strat_k_tv_r5 Qwen3-0.6b
    ;;
  06b_think)
    _launch bo_exec_06b_think_14strat_sweep bo_exec_06b_think_14strat_k_tv_r20 bo_exec_06b_think_14strat_k_tv_r5 Qwen3-0.6b_think
    ;;
  grpo_5ep)
    _launch bo_exec_06b_grpo_5ep_14strat_sweep bo_exec_06b_grpo_5ep_14strat_k_tv_r20 bo_exec_06b_grpo_5ep_14strat_k_tv_r5 Qwen3-0.6b-sc2-executor-grpo-2x-5ep_think
    ;;
  27b)
    _launch bo_exec_27b_14strat_sweep bo_exec_27b_14strat_k_tv_r20 bo_exec_27b_14strat_k_tv_r5 Qwen35-27b
    ;;
  all)
    _launch bo_exec_06b_14strat_sweep bo_exec_06b_14strat_k_tv_r20 bo_exec_06b_14strat_k_tv_r5 Qwen3-0.6b
    _launch bo_exec_06b_think_14strat_sweep bo_exec_06b_think_14strat_k_tv_r20 bo_exec_06b_think_14strat_k_tv_r5 Qwen3-0.6b_think
    _launch bo_exec_06b_grpo_5ep_14strat_sweep bo_exec_06b_grpo_5ep_14strat_k_tv_r20 bo_exec_06b_grpo_5ep_14strat_k_tv_r5 Qwen3-0.6b-sc2-executor-grpo-2x-5ep_think
    _launch bo_exec_27b_14strat_sweep bo_exec_27b_14strat_k_tv_r20 bo_exec_27b_14strat_k_tv_r5 Qwen35-27b
    ;;
  *)
    echo "Unknown variant: $VARIANT" >&2
    echo "Use: 06b | 06b_think | grpo_5ep | 27b | all" >&2
    exit 1
    ;;
esac

echo ""
echo "Attach examples:"
echo "  tmux attach -t bo_exec_06b_14strat_sweep"
echo "  tmux attach -t bo_exec_06b_think_14strat_sweep"
echo "  tmux attach -t bo_exec_06b_grpo_5ep_14strat_sweep"
echo "  tmux attach -t bo_exec_27b_14strat_sweep"
