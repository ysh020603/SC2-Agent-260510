#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source /home/wyq/miniconda3/etc/profile.d/conda.sh
conda activate SC2_0615

export SC2PATH="${SC2PATH:-/data2/SC2/StarCraftII/}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

BATCH_NAME="${BATCH_NAME:-kimi_nothink_v7_strategies}"
CONCURRENCY="${CONCURRENCY:-3}"
REPEATS="${REPEATS:-2}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
START_INDEX="${START_INDEX:-0}"
INDEX_BASE="${INDEX_BASE:-0}"
SKIP_COMPLETED="${SKIP_COMPLETED:-0}"
EXCLUDE_DIFFICULTIES="${EXCLUDE_DIFFICULTIES:-}"
JOB_STRIDE="${JOB_STRIDE:-1}"
JOB_OFFSET="${JOB_OFFSET:-0}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
NAMING_MODEL="${NAMING_MODEL:-Kimi-k2.5}"
ORDERING_MODEL="${ORDERING_MODEL:-Kimi-k2.5}"
EXECUTOR_MODEL="${EXECUTOR_MODEL:-Kimi-k2.5}"
DECISION_MODE="${DECISION_MODE:-three-stage}"
DIFFICULTIES="${DIFFICULTIES:-medium,mediumhard,hard,harder,veryhard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-random}"
MAPS="${MAPS:-KairosJunctionLE,AutomatonLE,AbyssalReefLE}"
STRATEGIES="${STRATEGIES:-bio,safe_tvt_raven,three_rax_stim,two_base_tanks,tank_thor_mech,battle_cruisers}"
LOG_SUFFIX="${LOG_SUFFIX:-}"
# If 1, exit when sweep finishes instead of waiting for Enter (for unattended resume).
AUTO_EXIT="${AUTO_EXIT:-0}"
# Peak-hour pause for NEW jobs, e.g. 09:00-12:00,14:00-18:00 (Asia/Shanghai).
PAUSE_HHMM_WINDOWS="${PAUSE_HHMM_WINDOWS:-}"
PAUSE_TIMEZONE="${PAUSE_TIMEZONE:-Asia/Shanghai}"
SCHEDULE_BALANCE="${SCHEDULE_BALANCE:-}"

LOG_OUT="game_records/${BATCH_NAME}${LOG_SUFFIX}_stdout.log"
LOG_ERR="game_records/${BATCH_NAME}${LOG_SUFFIX}_stderr.log"
mkdir -p game_records

echo "=== Strategy sweep ==="
echo "Batch: ${BATCH_NAME} | Concurrency: ${CONCURRENCY} | Start: ${START_INDEX} | Index base: ${INDEX_BASE} | Skip completed: ${SKIP_COMPLETED}"
echo "Shard: stride=${JOB_STRIDE} offset=${JOB_OFFSET}"
echo "Exclude difficulties: ${EXCLUDE_DIFFICULTIES:-'(none)'}"
echo "Schedule balance: ${SCHEDULE_BALANCE:-'(none)'}"
echo "Max attempts: ${MAX_ATTEMPTS}"
echo "Models: naming=${NAMING_MODEL} ordering=${ORDERING_MODEL} executor=${EXECUTOR_MODEL}"
echo "Decision mode: ${DECISION_MODE}"
echo "Difficulties: ${DIFFICULTIES}"
echo "Enemy races: ${ENEMY_RACES}"
echo "Enemy build: ${ENEMY_BUILD}"
echo "Maps: ${MAPS}"
echo "Strategies: ${STRATEGIES}"
echo "Pause windows: ${PAUSE_HHMM_WINDOWS:-'(none)'} tz=${PAUSE_TIMEZONE}"

SWEEP_ARGS=(
  --batch-name "${BATCH_NAME}"
  --concurrency "${CONCURRENCY}"
  --repeats "${REPEATS}"
  --game-time-limit "${GAME_TIME_LIMIT}"
  --start-index "${START_INDEX}"
  --index-base "${INDEX_BASE}"
  --job-stride "${JOB_STRIDE}"
  --job-offset "${JOB_OFFSET}"
  --max-attempts "${MAX_ATTEMPTS}"
  --naming-model "${NAMING_MODEL}"
  --ordering-model "${ORDERING_MODEL}"
  --executor-model "${EXECUTOR_MODEL}"
  --decision-mode "${DECISION_MODE}"
  --strategies "${STRATEGIES}"
  --difficulties "${DIFFICULTIES}"
  --enemy-races "${ENEMY_RACES}"
  --enemy-build "${ENEMY_BUILD}"
  --maps "${MAPS}"
)
if [[ "${SKIP_COMPLETED}" == "1" || "${SKIP_COMPLETED}" == "true" ]]; then
  SWEEP_ARGS+=(--skip-completed)
fi
if [[ -n "${EXCLUDE_DIFFICULTIES}" ]]; then
  SWEEP_ARGS+=(--exclude-difficulties "${EXCLUDE_DIFFICULTIES}")
fi
if [[ -n "${PAUSE_HHMM_WINDOWS}" ]]; then
  SWEEP_ARGS+=(--pause-hhmm-windows "${PAUSE_HHMM_WINDOWS}")
  SWEEP_ARGS+=(--pause-timezone "${PAUSE_TIMEZONE}")
fi
if [[ -n "${SCHEDULE_BALANCE}" ]]; then
  SWEEP_ARGS+=(--schedule-balance "${SCHEDULE_BALANCE}")
fi

set +e
python tools/run_kimi_nothink_strategy_sweep.py "${SWEEP_ARGS[@]}" \
  2>"${LOG_ERR}" | tee -a "${LOG_OUT}"
sweep_rc=${PIPESTATUS[0]}
set -e

echo ""
echo "[DONE] Sweep finished with exit=${sweep_rc}."
if [[ "${AUTO_EXIT}" == "1" || "${AUTO_EXIT}" == "true" ]]; then
  exit "${sweep_rc}"
fi
echo "Press Enter to close."
read -r _
exit "${sweep_rc}"
