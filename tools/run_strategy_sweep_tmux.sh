#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source /home/wyq/miniconda3/etc/profile.d/conda.sh
conda activate SC2_0615

export SC2PATH="${SC2PATH:-/data2/SC2/StarCraftII/}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

BATCH_NAME="${BATCH_NAME:-kimi_nothink_v7_strategies}"
CONCURRENCY="${CONCURRENCY:-3}"
REPEATS="${REPEATS:-2}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
START_INDEX="${START_INDEX:-0}"
NAMING_MODEL="${NAMING_MODEL:-Kimi-k2.5}"
ORDERING_MODEL="${ORDERING_MODEL:-Kimi-k2.5}"
EXECUTOR_MODEL="${EXECUTOR_MODEL:-Kimi-k2.5}"
DECISION_MODE="${DECISION_MODE:-three-stage}"
DIFFICULTIES="${DIFFICULTIES:-medium,mediumhard,hard,harder,veryhard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-random}"
MAPS="${MAPS:-KairosJunctionLE,AutomatonLE,AbyssalReefLE}"
STRATEGIES="${STRATEGIES:-bio,safe_tvt_raven,three_rax_stim,two_base_tanks,tank_thor_mech,battle_cruisers}"

LOG_OUT="game_records/${BATCH_NAME}_stdout.log"
LOG_ERR="game_records/${BATCH_NAME}_stderr.log"
mkdir -p game_records

echo "=== Strategy sweep ==="
echo "Batch: ${BATCH_NAME} | Concurrency: ${CONCURRENCY} | Start: ${START_INDEX}"
echo "Models: naming=${NAMING_MODEL} ordering=${ORDERING_MODEL} executor=${EXECUTOR_MODEL}"
echo "Decision mode: ${DECISION_MODE}"
echo "Difficulties: ${DIFFICULTIES}"
echo "Enemy races: ${ENEMY_RACES}"
echo "Enemy build: ${ENEMY_BUILD}"
echo "Maps: ${MAPS}"
echo "Strategies: ${STRATEGIES}"

python tools/run_kimi_nothink_strategy_sweep.py \
  --batch-name "${BATCH_NAME}" \
  --concurrency "${CONCURRENCY}" \
  --repeats "${REPEATS}" \
  --game-time-limit "${GAME_TIME_LIMIT}" \
  --start-index "${START_INDEX}" \
  --naming-model "${NAMING_MODEL}" \
  --ordering-model "${ORDERING_MODEL}" \
  --executor-model "${EXECUTOR_MODEL}" \
  --decision-mode "${DECISION_MODE}" \
  --strategies "${STRATEGIES}" \
  --difficulties "${DIFFICULTIES}" \
  --enemy-races "${ENEMY_RACES}" \
  --enemy-build "${ENEMY_BUILD}" \
  --maps "${MAPS}" \
  2>"${LOG_ERR}" | tee -a "${LOG_OUT}"

echo ""
echo "[DONE] Sweep finished. Press Enter to close."
read -r _
