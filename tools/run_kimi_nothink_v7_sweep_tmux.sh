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

LOG_OUT="game_records/${BATCH_NAME}_stdout.log"
LOG_ERR="game_records/${BATCH_NAME}_stderr.log"
mkdir -p game_records

echo "=== Kimi non-thinking v7 strategy sweep ==="
echo "Batch: ${BATCH_NAME} | Concurrency: ${CONCURRENCY} | Start: ${START_INDEX}"

python tools/run_kimi_nothink_strategy_sweep.py \
  --batch-name "${BATCH_NAME}" \
  --concurrency "${CONCURRENCY}" \
  --repeats "${REPEATS}" \
  --game-time-limit "${GAME_TIME_LIMIT}" \
  --start-index "${START_INDEX}" \
  2>"${LOG_ERR}" | tee -a "${LOG_OUT}"

echo ""
echo "[DONE] Sweep finished. Press Enter to close."
read -r _
