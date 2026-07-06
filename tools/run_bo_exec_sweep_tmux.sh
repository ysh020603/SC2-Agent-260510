#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source /home/wyq/miniconda3/etc/profile.d/conda.sh
conda activate SC2_0615

export SC2PATH="${SC2PATH:-/data2/SC2/StarCraftII/}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

BATCH_NAME="${BATCH_NAME:-bo_exec_grpo_10strat_macro_r5}"
CONCURRENCY="${CONCURRENCY:-20}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
START_INDEX="${START_INDEX:-0}"
SKIP_COMPLETED="${SKIP_COMPLETED:-1}"
EXECUTOR_MODEL="${EXECUTOR_MODEL:-Qwen3-1.7b-sc2-executor-grpo-2x-4ep_think}"
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
STRATEGIES="${STRATEGIES:-bio,safe_tvt_raven,three_rax_stim,two_base_tanks,tank_thor_mech,battle_cruisers,marine_rush,rusty,banshees,raven_liberator_tank}"

LOG_OUT="game_records/${BATCH_NAME}_stdout.log"
LOG_ERR="game_records/${BATCH_NAME}_stderr.log"
mkdir -p game_records

echo "=== BO-list executor sweep ==="
echo "Batch: ${BATCH_NAME} | Concurrency: ${CONCURRENCY} | Start: ${START_INDEX}"
echo "Executor: ${EXECUTOR_MODEL}"
echo "Difficulties: ${DIFFICULTIES}"
echo "Enemy races: ${ENEMY_RACES}"
echo "Enemy build: ${ENEMY_BUILD}"
echo "Maps: ${MAPS}"
echo "Strategies: ${STRATEGIES}"

SWEEP_ARGS=(
  --batch-name "${BATCH_NAME}"
  --concurrency "${CONCURRENCY}"
  --repeats "${REPEATS}"
  --game-time-limit "${GAME_TIME_LIMIT}"
  --start-index "${START_INDEX}"
  --executor-model "${EXECUTOR_MODEL}"
  --strategies "${STRATEGIES}"
  --difficulties "${DIFFICULTIES}"
  --enemy-races "${ENEMY_RACES}"
  --enemy-build "${ENEMY_BUILD}"
  --maps "${MAPS}"
)
if [[ "${SKIP_COMPLETED}" == "1" ]]; then
  SWEEP_ARGS+=(--skip-completed)
fi

python tools/run_bo_list_strategy_sweep.py \
  "${SWEEP_ARGS[@]}" \
  2>"${LOG_ERR}" | tee -a "${LOG_OUT}"

echo ""
echo "[DONE] Sweep finished. Press Enter to close."
read -r _
